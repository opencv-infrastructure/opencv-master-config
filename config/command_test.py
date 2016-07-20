from buildbot.steps.shell import ShellCommand
from buildbot.status.results import SUCCESS, FAILURE

class CommandTest(ShellCommand):
    def __init__(self, stage=None, module=None, moduleset=None, **kwargs):
        ShellCommand.__init__(self, **kwargs)
        self.testsLogs = {}
        self.testsPassed = []
        self.testsFailed = []
        self.all_tests_passed = False
        self.disabledTestsCount = 0

    def createSummary(self, log):
        if len(self.testsFailed) > 0 or len(self.testsPassed) > 0:
            self.addHTMLLog('tests summary', self.createTestsSummary())

    def describe(self, done=False):
        if done:
            res = [self.name + " ;"]
            res.append("passed: %d ;" % len(self.testsPassed))
            if len(self.testsFailed) > 0:
                res.append("failed: %d ;" % len(self.testsFailed))
            if self.disabledTestsCount > 0:
                res.append("skipped: %d ;" % self.disabledTestsCount)
            return res
        else:
            return [self.name]

    def getTestLogHtml(self, id):
        if id in self.testsLogs:
            return "<br/>".join(self.testsLogs[id])
        return ""

    def addFinishedTest(self, name, log = [], passed = True):
        if passed:
            self.testsPassed.append(name)
        else:
            self.testsFailed.append(name)
            self.testsLogs[name] = list(log)

    def evaluateCommand(self, cmd):
        r = ShellCommand.evaluateCommand(self, cmd)
        if r != SUCCESS:
            return r
        if self.all_tests_passed == True:
            if len(self.testsFailed) > 0:
                return FAILURE
            else:
                return SUCCESS
        else:
            return FAILURE

    def createTestsSummary (self):
        # Create a string with your html report and return it
        passed = len(self.testsPassed)
        failed = len(self.testsFailed)
        s = ""
        s += "Total tests:  " + str(passed + failed) + "<br>"
        s += "Tests failed: " + str(failed) + "<br>"
        s += "Tests passed: " + str(passed) + "<br>"
        if (self.disabledTestsCount > 0):
            s += "Disabled: %d" % self.disabledTestsCount + "<br><br>"

        if self.all_tests_passed == True:
            if len(self.testsFailed) > 0:
                s += "List failed tests (first 10): <br>"
                s += "<ul>"
                for i in range(min(10, len(self.testsFailed))):
                    testname = self.testsFailed[i]
                    logs = self.getTestLogHtml(testname)
                    s += "<li>" + testname
                    if len(logs) > 0:
                        s += " : <br/>"
                        s += "<font color='red' size=-1><pre>" + logs + "</pre></font>"
                    s += '\n'
                if len(self.testsFailed) > 10:
                    s += '<li>...\n'
                s += "</ul><br>"

            if len(self.testsPassed) > 0:
                s += "List passed tests (first 10): <br>"
                s += "<ul>"
                for i in range(min(10, len(self.testsPassed))):
                    s += "<li>%s\n" % str(self.testsPassed[i])
                if len(self.testsPassed) > 10:
                    s += '<li>...\n'
                s += "</ul><br>"

        else:
            s += '<font color="red" size=+1> Exception has been thrown. Please see stdio log. </font>'

        return s
