# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from mistral.engine import dispatcher
from mistral.tests.unit import base
from mistral.workflow import commands


def _print_commands(cmds):
    print("commands:")

    for cmd in cmds:
        if isinstance(cmd, commands.RunTask):
            print("%s, %s, %s" % (type(cmd), cmd.is_waiting(), cmd.unique_key))
        else:
            print("%s" % type(cmd))


class CommandDispatcherTest(base.BaseTest):
    def setUp(self):
        super(CommandDispatcherTest, self).setUp()

    def test_rearrange_commands(self):
        no_wait = commands.RunTask(None, None, None, None)
        fail = commands.FailWorkflow(None, None, None, None)
        succeed = commands.SucceedWorkflow(None, None, None, None)

        wait1 = commands.RunTask(None, None, None, None)
        wait1.wait = True
        wait1.unique_key = 'wait1'

        wait2 = commands.RunTask(None, None, None, None)
        wait2.wait = True
        wait2.unique_key = 'wait2'

        wait3 = commands.RunTask(None, None, None, None)
        wait3.wait = True
        wait3.unique_key = 'wait3'

        # 'set state' command is the first, others must be ignored.
        initial = [fail, no_wait, wait1, wait3, wait2]
        expected = [fail]

        cmds = dispatcher._rearrange_commands(initial)

        self.assertEqual(expected, cmds)

        # 'set state' command is the last, tasks before it must be sorted.
        initial = [no_wait, wait2, wait1, wait3, succeed]
        expected = [no_wait, wait1, wait2, wait3, succeed]

        cmds = dispatcher._rearrange_commands(initial)

        self.assertEqual(expected, cmds)

        # 'set state' command is in the middle, tasks before it must be sorted
        # and the task after it must be ignored.
        initial = [wait3, wait2, no_wait, succeed, wait1]
        expected = [no_wait, wait2, wait3, succeed]

        cmds = dispatcher._rearrange_commands(initial)

        self.assertEqual(expected, cmds)
