#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: schema.py
#
# Copyright 2020 Marcel Bezemer
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

from schema import Schema, And, Or, Optional

__author__ = '''Marcel Bezemer <mbezemer@schubergphilis.com>'''
__docformat__ = '''google'''
__date__ = '''03-02-2020'''
__copyright__ = '''Copyright 2020, Marcel Bezemer'''
__credits__ = ["Marcel Bezemer", "Costas Tyfoxylos"]
__license__ = '''MIT'''
__maintainer__ = '''Marcel Bezemer'''
__email__ = '''<mbezemer@schubergphilis.com>'''
__status__ = '''Development'''  # "Prototype", "Development", "Production".

AWS_SCHEMA = Schema({"name": "aws",
                     "arguments": {
                         "endpoint": And(str, len),
                         "certificate": And(str, len),
                         "private_key": And(str, len),
                         Optional("port"): And(int, lambda n: 1024 < n < 65000),
                         Optional("protocol"): And(str, len),
                         Optional("certificate_authority"): And(str, len),
                         Optional("device_location"): And(str, len)
                     }})

AZURE_SCHEMA = Schema({"name": "azure",
                       "arguments": {
                           "endpoint": And(str, len),
                           "key": And(str, len),
                           Optional("api_version"): And(str, len),
                           Optional("port"): And(int, lambda n: 1024 < n < 65000),
                           Optional("protocol"): And(str, len),
                           Optional("certificate_authority"): And(str, len)
                       }})

GOOGLE_SCHEMA = Schema({"name": "google",
                        "arguments": {
                            "project_id": And(str, len),
                            "cloud_region": And(str, len),
                            "registry_id": And(str, len),
                            "mqtt_bridge_hostname": And(str, len),
                            "mqtt_bridge_port": And(str, len),
                            "private_key": And(str, len),
                            Optional("port"): And(int, lambda n: 1024 < n < 65000),
                            Optional("protocol"): And(str, len),
                            Optional("certificate_authority"): And(str, len)
                        }})

PROVIDERS_SCHEMA = Or(AZURE_SCHEMA, AWS_SCHEMA, GOOGLE_SCHEMA)
CONFIGURATION_SCHEMA = Schema({"providers": [PROVIDERS_SCHEMA],
                               "device_name": And(str, len)})
