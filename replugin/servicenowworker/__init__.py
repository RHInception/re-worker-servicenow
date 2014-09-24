# -*- coding: utf-8 -*-
# Copyright © 2014 SEE AUTHORS FILE
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
ServiceNow worker.
"""
import os
import datetime
import json
import requests

from urllib import quote_plus

from reworker.worker import Worker


class ServiceNowWorkerError(Exception):
    """
    Base exception class for ServiceNowWorker errors.
    """
    pass


class ServiceNowWorker(Worker):
    """
    Worker which provides basic functionality with ServiceNow change records.
    """

    #: All allowed subcommands
    subcommands = (
        'DoesChangeRecordExist', 'UpdateStartTime',
        'UpdateEndTime')

    def _get_crq_ids(self, crq):
        """
        Returns the sys_id and number for a crq.

        *Parameters*:
            * crq: The Change Record name.
        """
        url = self._config['api_root_url'] + '/table/change_request'
        url += '?sysparm_query=%s&sysparm_fields=number,sys_id&sysparm_limit=1' % (
            quote_plus('number=' + crq))

        response = requests.get(
            url,
            auth=(
                self._config['servicenow_user'],
                self._config['servicenow_password']),
            headers={'Accept': 'application/json'})

        # we should get a 200, else it doesn't exist or server issue
        if response.status_code == 200:
            result = response.json()['result'][0]
            return {'number': result['number'], 'sys_id': result['sys_id']}
        return {'number': None, 'sys_id': None}

    def does_change_record_exist(self, body, output):
        """
        Subcommand which checks to see if a change record exists.

        *Dynamic Parameters Requires*:
            * change_record: the record to look for.
        """
        # TODO: Use _get_crq_ids
        expected_record = body.get('dynamic', {}).get('change_record', None)
        if not expected_record:
            raise ServiceNowWorkerError(
                'No change_record to search for given.')

        output.info('Checking for change record %s ...' % expected_record)

        # service now call
        url = self._config['api_root_url'] + '/table/change_request'
        url += '?sysparm_query=%s&sysparm_fields=number&sysparm_limit=2' % (
            quote_plus('number=' + expected_record))

        response = requests.get(
            url,
            auth=(
                self._config['servicenow_user'],
                self._config['servicenow_password']),
            headers={'Accept': 'application/json'})

        # we should get a 200, else it doesn't exist or server issue
        if response.status_code == 200:
            change_record = response.json()['result'][0]['number']
            if change_record == expected_record:
                output.info('found change record %s' % change_record)
                return {'status': 'completed', 'data': {'exists': True}}
        # 404 means it can't be found
        elif response.status_code == 404:
            output.info('change record %s does not exist.' % expected_record)
            return {'status': 'completed', 'data': {'exists': False}}
        # anything else is an error
        raise ServiceNowWorkerError('api returned %s instead of 200' % (
            response.status_code))

    def update_time(self, body, output, kind):
        """
        Subcommand which updates timing in Service Now.

        *Parameters*:
            * body: The message body.
            * output: The output instance back to the user.
            * kind: start or end

        *Dynamic Parameters Requires*:
            * change_record: the record to look for.
            * environment: the environment record to update
        """
        change_record = body.get('dynamic', {}).get('change_record', None)
        environment = body.get('dynamic', {}).get('environment', None)
        if not change_record:
            raise ServiceNowWorkerError('No change_record was given.')
        if not environment:
            raise ServiceNowWorkerError('No environment was given.')

        output.info('Updating the %s %s time for %s ...' % (
            environment, kind, change_record))

        # Get the sys_id
        sys_id = self._get_crq_ids(change_record)['sys_id']

        # We should get a 200, else it doesn't exist or server issue
        if sys_id:
            output.info('Found change record %s with sys_id %s' % (
                change_record, sys_id))
            # Now we have the sys_id, we should be able to update the time
            key = 'u_%s_%s_time' % (environment, kind)
            value = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            payload = {
                key: value,
            }
            record_url = self._config['api_root_url'] + '%s%s' % (
                '/table/change_request/', sys_id)
            response = requests.put(
                record_url,
                auth=(
                    self._config['servicenow_user'],
                    self._config['servicenow_password']),
                headers={'Accept': 'application/json'},
                data=json.dumps(payload))
            # Return success if we have a 200, else fall into the
            # "Anything else is an error" below
            if response.status_code == 200:
                return {'status': 'completed', 'data': {key: value}}

        output.error('Could not update timing due to missing change record')
        # Anything else is an error
        raise ServiceNowWorkerError('API returned %s instead of 200' % (
            response.status_code))
    # ---

    def process(self, channel, basic_deliver, properties, body, output):
        """
        Writes out output messages from the bus.

        *Keys Requires*:
            * subcommand: the subcommand to execute.
        """
        # Ack the original message
        self.ack(basic_deliver)
        corr_id = str(properties.correlation_id)

        try:
            try:
                subcommand = str(body['parameters']['subcommand'])
                if subcommand not in self.subcommands:
                    raise KeyError()
            except KeyError:
                raise ServiceNowWorkerError(
                    'No valid subcommand given. Nothing to do!')

            if subcommand == 'DoesChangeRecordExist':
                self.app_logger.info(
                    'Executing subcommand %s for correlation_id %s' % (
                        subcommand, corr_id))
                result = self.does_change_record_exist(body, output)
            elif subcommand == 'UpdateStartTime':
                self.app_logger.info(
                    'Executing subcommand %s for correlation_id %s' % (
                        subcommand, corr_id))
                result = self.update_time(body, output, 'start')
            elif subcommand == 'UpdateEndTime':
                self.app_logger.info(
                    'Executing subcommand %s for correlation_id %s' % (
                        subcommand, corr_id))
                result = self.update_time(body, output, 'end')
            else:
                self.app_logger.warn(
                    'Could not the implementation of subcommand %s' % (
                        subcommand))
                raise ServiceNowWorkerError('No subcommand implementation')

            # Send results back
            self.send(
                properties.reply_to,
                corr_id,
                result,
                exchange=''
            )

            # Notify on result. Not required but nice to do.
            self.notify(
                'ServiceNowWorker Executed Successfully',
                'ServiceNowWorker successfully executed %s. See logs.' % (
                    subcommand),
                'completed',
                corr_id)

            # Send out responses
            self.app_logger.info(
                'ServiceNowWorker successfully executed %s for '
                'correlation_id %s. See logs.' % (
                    subcommand, corr_id))

        except ServiceNowWorkerError, fwe:
            # If a ServiceNowWorkerError happens send a failure log it.
            self.app_logger.error('Failure: %s' % fwe)
            self.send(
                properties.reply_to,
                corr_id,
                {'status': 'failed'},
                exchange=''
            )
            self.notify(
                'ServiceNowWorker Failed',
                str(fwe),
                'failed',
                corr_id)
            output.error(str(fwe))


def main():  # pragma: no cover
    from reworker.worker import runner
    runner(ServiceNowWorker)


if __name__ == '__main__':  # pragma nocover
    main()
