import re
from buildbot.process.buildstep import LogLineObserver
from command_test import CommandTest

class CommandTestJava(CommandTest):
    def __init__(self, **kwargs):
        CommandTest.__init__(self, **kwargs)
        self.addLogObserver('stdio', JavaUnitTestsObserver())

    def createSummary(self, log):
        CommandTest.createSummary(self, log)
        self.addHTMLLog('junit-report-html', self.getLog("junit-report").getText())

class JavaUnitTestsObserver(LogLineObserver):
    test_started = re.compile(r'Running org.opencv.test.(\S+)')
    test_finished = re.compile(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+), Time elapsed: ([\d\.]+) sec')
    test_stat = re.compile(r'^BUILD SUCCESSFUL$')

    def __init__(self):
        LogLineObserver.__init__(self)
        self.testName = ""

    def outLineReceived(self, line):
        line = line.strip() # remove CR on Windows
        result = self.test_started.search(line)
        if result:
            self.testName = result.group(1)
            return

        if len(self.testName) > 0:
            result = self.test_finished.search(line)
            if result:
                err = int(result.group(2)) + int(result.group(3))
                self.step.addFinishedTest(self.testName, passed = (err == 0))
                self.step.disabledTestsCount += int(result.group(4))
                self.testName = ""
                return

        result = self.test_stat.search(line)
        if result:
            self.step.all_tests_passed = True
            return
