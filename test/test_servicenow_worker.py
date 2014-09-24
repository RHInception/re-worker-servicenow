# Copyright (C) 2014 SEE AUTHORS FILE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Unittests.
"""

import pika
import mock
import requests

from contextlib import nested

from . import TestCase

from replugin import servicenowworker


MQ_CONF = {
    'server': '127.0.0.1',
    'port': 5672,
    'vhost': '/',
    'user': 'guest',
    'password': 'guest',
}


class TestServiceNowWorker(TestCase):

    def setUp(self):
        """
        Set up some reusable mocks.
        """
        TestCase.setUp(self)

        self.channel = mock.MagicMock('pika.spec.Channel')

        self.channel.basic_consume = mock.Mock('basic_consume')
        self.channel.basic_ack = mock.Mock('basic_ack')
        self.channel.basic_publish = mock.Mock('basic_publish')

        self.basic_deliver = mock.MagicMock()
        self.basic_deliver.delivery_tag = 123

        self.properties = mock.MagicMock(
            'pika.spec.BasicProperties',
            correlation_id=123,
            reply_to='me')

        self.logger = mock.MagicMock('logging.Logger').__call__()
        self.app_logger = mock.MagicMock('logging.Logger').__call__()
        self.connection = mock.MagicMock('pika.SelectConnection')

    def tearDown(self):
        """
        After every test.
        """
        TestCase.tearDown(self)
        self.channel.reset_mock()
        self.channel.basic_consume.reset_mock()
        self.channel.basic_ack.reset_mock()
        self.channel.basic_publish.reset_mock()

        self.basic_deliver.reset_mock()
        self.properties.reset_mock()

        self.logger.reset_mock()
        self.app_logger.reset_mock()
        self.connection.reset_mock()

    def test_bad_command(self):
        """
        If a bad command is sent the worker should fail.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get')) as (_, _, _, get):

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "this is not a thing",
                },
                "dynamic": {
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_does_change_record_exist_return_properly_on_missing_record(self):
        """
        does_change_record_exist should return false if the API returns a 404
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get')) as (_, _, _, get):

            http_response = requests.Response()
            http_response.status_code = 404
            get.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "DoesChangeRecordExist",
                },
                "dynamic": {
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'
            assert worker.send.call_args[0][2]['data']['exists'] is False

    def test_does_change_record_exist_fails_on_non_200_404_response(self):
        """
        does_change_record_exist should fail if the api returns non 200/404
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get')) as (_, _, _, get):

            http_response = requests.Response()
            http_response.status_code = 400
            get.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "DoesChangeRecordExist",
                },
                "dynamic": {
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_does_change_record_exist(self):
        """
        Verifies checking for change records results in the proper responses.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get')) as (_, _, _, get):

            http_response = requests.Response()
            http_response.status_code = 200
            http_response.json = lambda: {
                u'result': [{
                    u'number': u'0000'}]}
            get.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "DoesChangeRecordExist",
                },
                "dynamic": {
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'
            assert worker.send.call_args[0][2]['data']['exists'] is True

    def test_does_change_record_exist_requires_change_record(self):
        """
        If no change_record is given to does_change_record exist it should
        fail
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get')) as (_, _, _, get):

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "DoesChangeRecordExist",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'
    # ---

    def test_update_time(self):
        """
        Verify we can update a start time.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get'),
                mock.patch('requests.put')) as (_, _, _, get, put):

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            get_response = requests.Response()
            get_response.status_code = 200
            get_response.json = lambda: {
                u'result': [{
                    u'number': '000000',
                    u'sys_id': u'0000'}]}
            get.return_value = get_response

            put_response = requests.Response()
            put_response.status_code = 200
            put_response.json = lambda: {
                u'result': [{
                    u'sys_id': u'1234567890'}]}
            put.return_value = put_response

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "UpdateStartTime",
                },
                "dynamic": {
                    "environment": "qa",
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'
            #assert 'u_qa_start_time' in worker.send.call_args[0][2]['data'].keys()

    def test_update_time_server_id_failure(self):
        """
        Verify that missing sys_id object returns proper failure for update_time.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get'),
                mock.patch('requests.put')) as (_, _, _, get, put):

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            get_response = requests.Response()
            get_response.status_code = 200
            get_response.json = lambda: {
                u'result': [{
                    u'number': u'0000',
                    u'sys_id': u'0000'}]}
            get.return_value = get_response

            put_response = requests.Response()
            put_response.status_code = 404
            put_response.json = lambda: {
                u'error': [{
                    u'message': u'message here'}]}
            put.return_value = put_response

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "UpdateStartTime",
                },
                "dynamic": {
                    "environment": "qa",
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_update_time_missing_dynamic_data_failure(self):
        """
        Verify that missing dynamic data returns proper failure for update_time.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send')) as (
                    _, _, _):

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "UpdateStartTime",
                },
                "dynamic": {
                    "change_record": "0000",
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

            # Execute the call again with but this time without change_recorda
            del body['dynamic']['change_record']
            body['dynamic']['environment'] = 'qa'
            self.app_logger.error.reset_mock()
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'
