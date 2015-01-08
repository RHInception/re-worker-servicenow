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
import datetime

from contextlib import nested

from . import TestCase

from replugin import servicenowworker

# Abridged config for payload tests
WORKER_CONF = {
    "change_record_payload": {
        "u_change_location": "0503586769dd3000df63506980241089",
        "u_assignment_group": "f3b9bd00d0000000ec0be80b207ce954",
        "u_end_date": None,
        "u_change_plan": "Frobnicate all the things",
        "u_backout_plan": "Frob them back again",
        "u_short_description": "Test the Megafrobber Enterprise Suite",
        "u_start_date": None
    },
    "start_date_diff": {
        "days": 7
    },
    "end_date_diff": {
        "days": 7,
        "hours": 8
    }
}

MQ_CONF = {
    'server': '127.0.0.1',
    'port': 5672,
    'vhost': '/',
    'user': 'guest',
    'password': 'guest',
}

NOW = datetime.datetime.now()

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

    def test_does_c_task_exist_will_autocreate_if_configured_to_on_404(self):
        """
        does_c_task_exist should autocreate a ctask if configued to on 404.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.get'),
                mock.patch('requests.post')) as (_, _, _, get, post):

            http_response = requests.Response()
            http_response.status_code = 404
            get.return_value = http_response

            post_result = {
                'result': {
                    'number': 'CTASK0001234',
                    'change_request': {
                        'link': 'http://127.0.0.1/'
                    }
                }
            }

            post_response = requests.Response()
            post_response.status_code = 201
            post_response.json = lambda: post_result
            post.return_value = post_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._config['auto_create_c_task_if_missing'] = True
            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "DoesCTaskExist",
                },
                "dynamic": {
                    "change_record": "0000",
                    "ctask": "CTASK0001234"
                }
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert post.call_count == 1  # This is the ctask creation call
            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'


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

    def test_does_c_task_exist_return_properly_on_missing_record(self):
        """
        does_c_task_record_exist should return false if the API returns a 404
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
                    "subcommand": "DoesCTaskExist",
                },
                "dynamic": {
                    "ctask": "CTASK0001234",
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

    def test_does_c_task_exist(self):
        """
        Verifies checking for ctask records results in the proper responses.
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
                    u'number': u'CTASK0001234'}]}
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
                    "subcommand": "DoesCTaskExist",
                },
                "dynamic": {
                    "ctask": "CTASK0001234",
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

    def test_does_c_task_exist_fails_on_non_200_404_response(self):
        """
        does_c_task_exist should fail if the api returns non 200/404
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
                    "subcommand": "DoesCTaskExist",
                },
                "dynamic": {
                    "ctask": "CTASK0001234",
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

    def test_does_c_task_exist_requires_change_record(self):
        """
        If no ctask is given to does_ctask_record exist it should fail """
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
                    "subcommand": "DoesCTaskExist",
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

    def test__make_start_end_dates(self):
        """We can calculate start/end dates for changes

Expected results from method:

- u_start_date = now + start_diff
- u_end_date = now + end_diff
"""
        start_diff = {
            'days': 5
        }
        end_diff = {
            'days': 10
        }
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('replugin.servicenowworker.datetime.datetime')) as (
                    _, _, _, dt):

            dt.now.return_value = NOW
            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            diffs = worker._make_start_end_dates(start_diff, end_diff)
            self.assertEqual(
                diffs['u_start_date'],
                (NOW + datetime.timedelta(**start_diff)).strftime('%Y-%m-%d %H:%M:%S'))
            self.assertEqual(
                diffs['u_end_date'],
                (NOW + datetime.timedelta(**end_diff)).strftime('%Y-%m-%d %H:%M:%S'))

            # Now do the reverse, but swap the start/end dates so we
            # catch invalid date ranges
            with self.assertRaises(servicenowworker.ServiceNowWorkerError):
                worker._make_start_end_dates(end_diff, start_diff)

    def test_create_change_record(self):
        """We can create change records, and notice failures"""
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.post')) as (
                    _, _, _, post):

            result = {'import_set': 'ISET0011337',
                           'result': [
                               {'display_name': 'number',
                                'display_value': 'CHG0007331',
                                'record_link': 'https://example.service-now.com/api/now/table/change_request/d6e68a52fd5f31ff296db3236d1f6bfb',
                                'status': 'inserted',
                                'sys_id': 'd6e68a52fd5f31ff296db3236d1f6bfb',
                                'table': 'change_request',
                                'transform_map': 'Auto Transform Change Map'}
                           ],
                 'staging_table': 'u_test_change_creation'
            }

            http_response = requests.Response()
            http_response.status_code = 201
            http_response.json = lambda: result
            post.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)
            (chg, url) = worker.create_change_record(worker._config)

            self.assertEqual(chg, 'CHG0007331')
            self.assertEqual(url, 'https://example.service-now.com/api/now/table/change_request/d6e68a52fd5f31ff296db3236d1f6bfb')

            # Catch unauthorized requests
            with self.assertRaises(servicenowworker.ServiceNowWorkerError):
                http_response.status_code = 403
                (chg, url) = worker.create_change_record(worker._config)

            # catch 'wtf?' requests
            with self.assertRaises(servicenowworker.ServiceNowWorkerError):
                http_response.status_code = 500
                (chg, url) = worker.create_change_record(worker._config)

    def test_does_change_record_exist_auto_create_if_missing(self):
        """
        We call the auto-create method if a change record doesn't exist
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.create_change_record'),
                mock.patch('requests.get')) as (_, _, _, create_record, get):

            http_response = requests.Response()
            http_response.status_code = 404
            get.return_value = http_response
            create_record.return_value = ('CHG1337', 'http://example.servicenow.com/foobar')

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

            # Enable auto-create
            worker._config['auto_create_change_if_missing'] = True

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            self.assertEqual(self.app_logger.error.call_count, 0)
            self.assertEqual(worker.send.call_args[0][2]['status'], 'completed')
            self.assertTrue(worker.send.call_args[0][2]['data']['exists'])
            self.assertEqual(worker.send.call_args[0][2]['data']['new_record'], 'CHG1337')
            self.assertEqual(worker.send.call_args[0][2]['data']['new_record_url'], 'http://example.servicenow.com/foobar')
            create_record.assert_called_once()

    def test_create_c_task(self):
        """We can create ctasks"""
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.post')) as (
                    _, _, _, post):

            result = {
                'result': {
                    'number': 'CTASK0001234',
                    'change_request': {
                        'link': 'http://127.0.0.1/'
                    }
                }
            }

            http_response = requests.Response()
            http_response.status_code = 201
            http_response.json = lambda: result
            post.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "CreateCTask",
                },
                "dynamic": {
                    "change_record": "0000",
                    "ctask_description": "data stuff"
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

    def test_create_c_task_fails_properly_on_unknown_response(self):
        """We can understand the failure of ctask creation on unknwon response"""
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.post')) as (
                    _, _, _, post):

            result = {
                'result': {
                    'number': 'CTASK0001234',
                    'change_request': {
                        'link': 'http://127.0.0.1/'
                    }
                }
            }

            http_response = requests.Response()
            http_response.status_code = 500
            http_response.json = lambda: result
            post.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "CreateCTask",
                },
                "dynamic": {
                    "change_record": "0000",
                    "ctask_description": "data stuff"
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

    def test_create_c_task_fails_properly_on_bad_auth_response(self):
        """We can understand the failure of ctask creation on bad auth response"""
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.notify'),
                mock.patch('replugin.servicenowworker.ServiceNowWorker.send'),
                mock.patch('requests.post')) as (
                    _, _, _, post):

            result = {
                'result': {
                    'number': 'CTASK0001234',
                    'change_request': {
                        'link': 'http://127.0.0.1/'
                    }
                }
            }

            http_response = requests.Response()
            http_response.status_code = 403
            http_response.json = lambda: result
            post.return_value = http_response

            worker = servicenowworker.ServiceNowWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "servicenow",
                    "subcommand": "CreateCTask",
                },
                "dynamic": {
                    "change_record": "0000",
                    "ctask_description": "data stuff"
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
