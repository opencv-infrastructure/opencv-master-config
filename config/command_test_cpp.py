import re

from buildbot.process.buildstep import LogLineObserver
from buildbot.status.results import SUCCESS, FAILURE
from command_test import CommandTest

class CommandTestCPP(CommandTest):
    def __init__(self, **kwargs):
        CommandTest.__init__(self, **kwargs)
        self.addLogObserver('stdio', GoogleUnitTestsObserver())
        self.addLogObserver('stdio', ValgrindObserver())
        self.caseCount = 0
        self.testCount = 0
        self.valgrindSummary = ""
        self.valgrindErrors = 0
        self.valgrindLog = []

    def createSummary(self, log):
        CommandTest.createSummary(self, log)
        if len(self.valgrindSummary) > 0 or len(self.valgrindLog) > 0:
            self.addHTMLLog('valgrind summary', "<pre>%s</pre>" % "\n".join(self.valgrindLog))

    def describe(self, done=False):
        res = CommandTest.describe(self, done)
        if done:
            res.insert(1, "cases (tests): %d (%d) ;" % (self.caseCount, self.testCount))
            if self.valgrindErrors > 0:
                res.append("valgrind issues: %d ;" % self.valgrindErrors)
        return res

    def evaluateCommand(self, cmd):
        r = CommandTest.evaluateCommand(self, cmd)
        if r != SUCCESS:
            return r
        if self.valgrindErrors > 0:
            return FAILURE
        else:
            return SUCCESS

class GoogleUnitTestsObserver(LogLineObserver):
    test_started = re.compile(r'\[ RUN      \] (\S+)')
    test_failed =       re.compile(r'\[  FAILED  \] (\S+) \(\d+ ms\)')
    test_failed_perf =  re.compile(r'\[  FAILED  \] (\S+), where GetParam\(\) = \((.+)\) \(\d+ ms\)')
    test_passed =  re.compile(r'\[       OK \] (\S+) \(\d+ ms\)')

    test_stat_success = re.compile(r'\[  PASSED  \] \d+ (?:test|tests)\.')
    test_stat_total = re.compile(r'\[==========\] (\d+) (?:test|tests) from (\d+) test (?:case|cases) ran\. \((\d+) ms total\)')
    test_stat_disabled = re.compile(r'YOU HAVE (\d+) DISABLED TEST')

    def __init__(self):
        LogLineObserver.__init__(self)
        self.testLog = []

    def outLineReceived(self, line):
        # Test start
        result = self.test_started.search(line)
        if result:
            self.testLog = []
            return

        # Test failed
        result = self.test_failed.search(line) or self.test_failed_perf.search(line)
        if result:
            name = result.groups()[0]
            if len(result.groups()) > 1:
                name += " [" + result.groups()[1] + "]"
            self.step.addFinishedTest(name, self.testLog, passed=False)
            return

        # Test passed
        result = self.test_passed.search(line)
        if result:
            name = result.group(1)
            self.step.addFinishedTest(name, self.testLog, passed=True)
            return

        # Determine if tests passed
        result = self.test_stat_success.search(line)
        if result:
            self.step.all_tests_passed = True
            return

        # Gather disabled tests count
        result = self.test_stat_disabled.search(line)
        if result:
            self.step.disabledTestsCount = int(result.group(1))
            return

        result = self.test_stat_total.search(line)
        if result:
            self.step.caseCount = int(result.group(2))
            self.step.testCount = int(result.group(1))
            return

        self.testLog.append(line)

class ValgrindObserver(LogLineObserver):
    S_NONE = 1
    S_LOG = 2
    S_SUM = 3

    rx_start_sum = re.compile(r'==\d+== HEAP SUMMARY:\s*')
    rx_err_sum = re.compile(r'==\d+== ERROR SUMMARY:\s*((\d+) error.*)')
    rx_one = re.compile(r'==\d+==(.*)')

    def __init__(self):
        LogLineObserver.__init__(self)
        self.state = self.S_NONE

    def addLine(self, line):
        res = self.rx_one.search(line)
        if res:
            self.step.valgrindLog.append(res.group(1))
            return True
        return False

    def errLineReceived(self, line):
        found = self.addLine(line)
        if self.state == self.S_NONE:
            if found:
                self.state = self.S_LOG
        elif self.state == self.S_LOG:
            res = self.rx_start_sum.search(line)
            if res:
                self.state = self.S_SUM
        elif self.state == self.S_SUM:
            res = self.rx_err_sum.search(line)
            if res:
                self.state = self.S_NONE
                self.step.valgrindSummary = res.group(1)
                self.step.valgrindErrors = int(res.group(2))
