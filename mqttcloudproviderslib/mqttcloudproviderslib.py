#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: mqttcloudproviderslib.py
#
# Copyright 2020 Costas Tyfoxylos
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
#

"""
Main code for mqttcloudproviderslib.

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html

"""

import abc
import base64
import concurrent.futures
import datetime
import hmac
import importlib
import json
import logging
import ssl
import time
from urllib.parse import quote

import paho.mqtt.client as mqtt
from jwt import JWT

from .mqttcloudproviderslibexceptions import ProviderInstantiationError
from .schemas import (PROVIDERS_SCHEMA, CONFIGURATION_SCHEMA)

__author__ = '''Costas Tyfoxylos <ctyfoxylos@schubergphilis.com>'''
__docformat__ = '''google'''
__date__ = '''03-02-2020'''
__copyright__ = '''Copyright 2020, Costas Tyfoxylos'''
__credits__ = ["Costas Tyfoxylos", "Marcel Bezemer", "Frank Breedijk"]
__license__ = '''MIT'''
__maintainer__ = '''Costas Tyfoxylos'''
__email__ = '''<ctyfoxylos@schubergphilis.com>'''
__status__ = '''Development'''  # "Prototype", "Development", "Production".

# This is the main prefix used for logging
LOGGER_BASENAME = '''mqttcloudproviderslib'''
LOGGER = logging.getLogger(LOGGER_BASENAME)
LOGGER.addHandler(logging.NullHandler())


class MessageHub:
    """A fan provider to all cloud providers."""

    def __init__(self, configuration):
        self._configuration = CONFIGURATION_SCHEMA.validate(configuration)
        device_name = configuration.get('device_name', 'UNKNOWN_DEVICE_NAME')
        self._providers = [Provider(device_name=device_name, data=data)
                           for data in configuration.get('providers', [])]

    def _broadcast(self, method_name, message, topic=None):
        arguments = [argument for argument in (message, topic) if argument]
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(getattr(provider, method_name), *arguments) for provider in self._providers]
        return all(list(concurrent.futures.as_completed(futures)))

    def broadcast(self, message):
        """It will broadcast the provided message to all registered cloud provider's default topic.

        Args:
            message (dict): The message to publish to the default provider's topic.

        Returns:
            result (bool): True if all published messages get delivered, False if any fails.

        """
        return self._broadcast('publish', message)

    def broadcast_to_subtopic(self, message, topic):
        """It will broadcast the provided message to all registered cloud provider's with specified topic.

        Args:
            topic (str): The provider's specific topic to publish the message to.
            message (dict): The message to publish to the specified provider's topic.

        Returns:
            result (bool): True if all published messages get delivered, False if any fails.

        """
        return self._broadcast('publish_to_subtopic', message, topic)


class Provider:  # pylint: disable=too-few-public-methods
    """Placeholder."""

    def __new__(cls, device_name, data):
        try:
            data = PROVIDERS_SCHEMA.validate(data)
            provider = data.get('name')
            adapter = getattr(importlib.import_module('mqttcloudproviderslib.mqttcloudproviderslib'),
                              f'{provider.title()}Adapter')
            provider_adapter = adapter(device_name=device_name, **data.get('arguments'))
            return provider_adapter
        except Exception:
            raise ProviderInstantiationError(f'The data received could not instantiate any valid provider. '
                                             f'Data received :{data}')


class BaseAdapter(abc.ABC):
    """Placeholder."""

    def __init__(self, device_name, port, certificate_authority, protocol):
        self._logger = logging.getLogger(f'{LOGGER_BASENAME}.{self.__class__.__name__}')
        self.device_name = device_name
        self.port = port
        self.certificate_authority = certificate_authority
        self._protocol = protocol
        self._logger.debug('Trying to instantiate mqtt client for provider :"%s"', self.name)
        self._mqtt_client = self._get_mqtt_client()

    @property
    def name(self):
        """Placeholder."""
        return self.__class__.__name__.replace("Adapter", "")

    @property
    def protocol(self):
        """Placeholder."""
        return self._protocol

    @abc.abstractmethod
    def _get_mqtt_client(self):
        pass

    @abc.abstractmethod
    def _get_topic(self, topic=None):
        pass

    def _publish(self, message, topic=None):
        try:
            topic = self._get_topic(topic)
            result = self._mqtt_client.publish(topic, json.dumps(message))
            self._logger.debug('%s: return_code: %s, mid: %s, published: %s, topic: %s',
                               self.name, result.rc, result.mid, result.is_published(), topic)
            return result.is_published()
        except Exception:  # pylint: disable=broad-except
            self._logger.exception('Could not publish message')

    def publish(self, message):
        """Placeholder."""
        return self._publish(message)

    def publish_to_subtopic(self, message, topic):
        """Placeholder."""
        return self._publish(message, topic)

    @abc.abstractmethod
    def on_disconnect(self, client, user_data, return_code):
        """Placeholder."""
        pass


class AwsAdapter(BaseAdapter):
    """Placeholder."""

    def __init__(self,  # pylint: disable=too-many-arguments
                 device_name,
                 endpoint,
                 certificate,
                 private_key,
                 certificate_authority='AmazonRootCA1.pem',
                 port=443,
                 protocol='x-amzn-mqtt-ca',
                 device_location='devices'):
        self.endpoint = endpoint
        self.url = f'https://{endpoint}'
        self.certificate = certificate
        self.private_key = private_key
        self.device_location = device_location
        super().__init__(device_name, port, certificate_authority, protocol)

    def _get_ssl_context(self):
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.set_alpn_protocols([self.protocol])
            ssl_context.load_verify_locations(cafile=self.certificate_authority)
            ssl_context.load_cert_chain(certfile=self.certificate, keyfile=self.private_key)
            return ssl_context
        except Exception:
            self._logger.exception('Unable to get ssl context.')
            raise ProviderInstantiationError

    def _get_mqtt_client(self):
        try:
            mqtt_client = mqtt.Client()
            ssl_context = self._get_ssl_context()
            mqtt_client.tls_set_context(context=ssl_context)
            mqtt_client.on_disconnect = self.on_disconnect
            failure = mqtt_client.connect(self.endpoint, port=self.port)
            if not failure:
                return mqtt_client
            raise ProviderInstantiationError
        except Exception:
            self._logger.exception('Unable to create client and connect to mqtt service.')
            raise ProviderInstantiationError

    def _get_topic(self, topic=None):
        return f'{self.device_location}/{self.device_name}/events/{topic if topic else ""}'

    def on_disconnect(self, client, user_data, return_code):
        """Placeholder."""
        if return_code:
            self._mqtt_client.reconnect()


class AzureAdapter(BaseAdapter):
    """Placeholder."""

    def __init__(self,  # pylint: disable=too-many-arguments
                 device_name,
                 endpoint,
                 key,
                 api_version='2018-06-30',
                 certificate_authority='AzureRootCA.pem',
                 port=8883,
                 protocol=mqtt.MQTTv311):
        self.endpoint = endpoint
        self.device_name = device_name
        self.key = self._get_key_contents(key)
        self.certificate_authority = certificate_authority
        self.user = f'{endpoint}/{device_name}/?api-version={api_version}'
        super().__init__(device_name, port, certificate_authority, protocol)

    @staticmethod
    def _get_key_contents(key):
        with open(key, 'r') as key_file:
            result = key_file.read()
        return result

    @staticmethod
    def _generate_sas_token(uri, key, expiry=3600):
        ttl = int(time.time()) + expiry
        url_to_sign = quote(uri, safe='')
        hmac_ = hmac.new(base64.b64decode(key),
                         msg=f'{url_to_sign}\n{ttl}'.encode('utf-8'),
                         digestmod='sha256')
        signature = quote(base64.b64encode(hmac_.digest()), safe='')
        return f'SharedAccessSignature sr={url_to_sign}&sig={signature}&se={ttl}'

    def _get_mqtt_client(self):
        try:
            mqtt_client = mqtt.Client(client_id=self.device_name, protocol=self.protocol)
            mqtt_client.tls_set(self.certificate_authority)
            mqtt_client.username_pw_set(username=self.user, password=self._generate_sas_token(self.endpoint, self.key))
            mqtt_client.on_disconnect = self.on_disconnect
            failure = mqtt_client.connect(self.endpoint, port=self.port)
            if not failure:
                return mqtt_client
            raise ProviderInstantiationError
        except Exception:
            self._logger.exception('Unable to create client and connect to mqtt service.')
            raise ProviderInstantiationError

    def _get_topic(self, topic=None):
        topic = f'topic={topic}' if topic else ''
        return f'devices/{self.device_name}/messages/events/{topic}'

    def on_disconnect(self, client, user_data, return_code):
        """Placeholder."""
        if return_code:
            self._mqtt_client.username_pw_set(username=self.user,
                                              password=self._generate_sas_token(self.endpoint, self.key))
            self._mqtt_client.reconnect()


class GoogleAdapter(BaseAdapter):
    """Placeholder."""

    def __init__(self,  # pylint: disable=too-many-arguments
                 device_name,
                 project_id,
                 cloud_region,
                 registry_id,
                 mqtt_bridge_hostname,
                 mqtt_bridge_port,
                 private_key,
                 certificate_authority='GoogleRoots.pem',
                 port=8883,
                 protocol=ssl.PROTOCOL_TLSv1_2):
        self.project_id = project_id
        self.cloud_region = cloud_region
        self.registry_id = registry_id
        self.private_key = private_key
        self.mqtt_bridge_hostname = mqtt_bridge_hostname
        self.mqtt_bridge_port = mqtt_bridge_port
        self.client_id = (f'projects/{project_id}/locations/{cloud_region}/'
                          f'registries/{registry_id}/devices/{device_name}')
        super().__init__(device_name, port, certificate_authority, protocol)

    @staticmethod
    def _create_jwt(project_id, private_key, algorithm):
        """Creates a JWT (https://jwt.io) to establish an MQTT connection.

        Args:
            project_id: The cloud project ID this device belongs to
            private_key: A path to a file containing either an RSA256 or
            ES256 private key.
            algorithm: The encryption algorithm to use. Either 'RS256' or 'ES256'

        Returns:
            A JWT generated from the given project_id and private key, which
            expires in 20 minutes. After 20 minutes, your client will be
            disconnected, and a new JWT will have to be generated.

        Raises:
            ValueError: If the private_key does not contain a known key.

        """
        token = {'iat': datetime.datetime.utcnow(),
                 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
                 'aud': project_id}
        with open(private_key, 'r') as key_file:
            private_key_contents = key_file.read()
        return JWT().encode(token, private_key_contents, algorithm)

    def _get_mqtt_client(self):
        try:
            mqtt_client = mqtt.Client(client_id=self.client_id)
            # With Google Cloud IoT Core, the username field is ignored, and the
            # password field is used to transmit a JWT to authorize the device.
            mqtt_client.username_pw_set(username='unused', password=self._create_jwt(self.project_id,
                                                                                     self.private_key, "RS256"))
            mqtt_client.tls_set(ca_certs=self.certificate_authority, tls_version=self.protocol)
            mqtt_client.on_disconnect = self.on_disconnect
            failure = mqtt_client.connect(self.mqtt_bridge_hostname, self.mqtt_bridge_port)
            if not failure:
                return mqtt_client
            raise ProviderInstantiationError
        except Exception:
            self._logger.exception('Unable to create client and connect to mqtt service.')
            raise ProviderInstantiationError

    def _get_topic(self, topic=None):
        return f'/devices/{self.device_name}/events/{topic if topic else ""}'

    def on_disconnect(self, client, user_data, return_code):
        """Placeholder."""
        if return_code:
            self._mqtt_client.username_pw_set(username='unused', password=self._create_jwt(self.project_id,
                                                                                           self.private_key, "RS256"))
            self._mqtt_client.reconnect()
