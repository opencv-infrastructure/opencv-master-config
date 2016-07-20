import re

import buildbot.process.buildstep as buildstep

from command_test import CommandTest


class CommandTestPy(CommandTest):
    def __init__(self, **kwargs):
        CommandTest.__init__(self, **kwargs)
        self.addLogObserver('stdio', PythonUnitTestsObserver())

class PythonUnitTestsObserver(buildstep.LogLineObserver):
    test_failed = re.compile(r'FAIL: test_(\S+) \(__main__\.(\S+)\)')
    test_passed = re.compile(r'test_(\S+) \(__main__\.(\S+)\) \.\.\. [^E].*')
    test_stat_total = re.compile(r'Ran (\d+) tests in [\d\.]+s')

    def __init__(self):
        buildstep.LogLineObserver.__init__(self)

    def outLineReceived(self, line):
        result = self.test_stat_total.search(line)
        if result:
            self.step.all_tests_passed = True
            return

        result = self.test_failed.search(line)
        if result:
            name = result.group(1)
            self.step.addFinishedTest(name, passed = False)
            return

        result = self.test_passed.search(line)
        if result:
            name = result.group(1)
            self.step.addFinishedTest(name, passed = True)
            return
