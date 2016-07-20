import stat

from twisted.internet import defer

from buildbot.process.buildstep import BuildStep
from buildbot.process.remotecommand import RemoteCommand, RemoteShellCommand
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, SKIPPED


class CheckSize(BuildStep):
    def __init__(self, codebase, workdir, warnLimit=1024*1024, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.workdir = workdir
        self.codebase = codebase
        self.sz = 0
        self.warnLimit = warnLimit

    def getRevRange(self):
        base = self.getProperty('got_revision')
        if isinstance(base, dict):
            base = base[self.codebase]
        return '%s..HEAD' % (base)

    @defer.inlineCallbacks
    def run(self):
        l = yield self.addLog('stdio')
        cmd = RemoteShellCommand(
            self.workdir,
            ['git', 'bundle', 'create', 'test.bundle', self.getRevRange()],
            collectStdout=True
        )
        yield self.updateSummary()
        yield cmd.useLog(l)
        yield self.runCommand(cmd)
        if not cmd.didFail():
            cmd = RemoteCommand('stat', {'file': self.workdir + '/test.bundle'})
            yield cmd.useLog(l)
            yield self.runCommand(cmd)
            if not cmd.didFail():
                s = cmd.updates['stat'][-1]
                self.sz = s[stat.ST_SIZE]
                yield self.updateSummary()
                yield l.addStdout(u'"stat" returned: %s\n' % str(s))
                yield l.addStdout(u'File size: %s\n' % self.getSize(True))
                yield l.finish()
                if self.sz >= self.warnLimit:
                    defer.returnValue(WARNINGS)
                defer.returnValue(SUCCESS)
        yield l.finish()
        yield self.updateSummary()
        defer.returnValue(FAILURE)

    def getCurrentSummary(self):
        return {'step': u'running'}

    def getResultSummary(self):
        return {'step': self.codebase + ': ' + self.getSize(False)}

    def getSize(self, full=False):
        kib = self.sz / 1024
        mib = kib / 1024
        if full:
            return u'%s bytes = %s KiB = %s MiB' % (self.sz, kib, mib)
        return u'%s KiB' % kib
