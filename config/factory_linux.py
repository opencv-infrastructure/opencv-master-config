import re

from twisted.internet import defer

from buildbot.status.results import SUCCESS
from buildbot.steps.shell import ShellCommand, SetPropertyFromCommand, Compile
from buildbot.steps.slave import RemoveDirectory, MakeDirectory
from buildbot.process.properties import Interpolate

from build_utils import OSType, isNotBranch24, isBranch24
from factory_ocl import OCL_factory as BaseFactory


class AbiDumpCommand(ShellCommand):

    def __init__(self, builder, installPath, resultFile, **kwargs):
        logFile = "abi_log.txt"
        cmd = builder.envCmd.split() + [
            "abi-compliance-checker",
            "-l", "opencv",
            "-dump", "opencv_abi.xml",
            "-dump-path", resultFile,
            "-relpath", installPath,
            "-log-path", logFile,
        ]
        ShellCommand.__init__(self, workdir='build', command=cmd, logfiles={"log": logFile}, **kwargs)



class AbiFindBaseCommand(SetPropertyFromCommand):

    def __init__(self, builder, **kwargs):
        def extractor(rc, stdout, stderr):
            if rc == 0:
                for fname in self.getCandidates():
                    if fname in stdout:
                        print 'ABI: found', fname
                        return {'abi_base_file':'/opt/build-worker/abi/%s' % fname}
            print 'ABI: fallback to 3.4.0'
            return {'abi_base_file':'/opt/build-worker/abi/dump-3.4.0.abi.tar.gz'}
        cmd = builder.envCmd + 'ls -1 /opt/build-worker/abi/*.abi.tar.gz'
        SetPropertyFromCommand.__init__(self, workdir='build', command=cmd, extract_fn=extractor, **kwargs)


    def getCandidates(self):
        verString = self.getProperty('commit-description', '3.4.0')
        if isinstance(verString, dict):
            verString = verString['opencv']
        candidates = []
        counter = 5
        index = len(verString)
        while index > 0 and counter > 0:
            fname = 'dump-%s.abi.tar.gz' % verString[:index]
            candidates.append(fname)
            index = verString.rfind('-', 0, index)
            counter = counter - 1
        return candidates



class AbiCompareCommand(ShellCommand):

    def __init__(self, builder, resultFile, **kwargs):
        reportFile = "abi_report.html"
        logFile = "abi_log.txt"  # TODO Used?
        cmd = builder.envCmd.split() + [
            "abi-compliance-checker",
            "-l", "opencv",
            "-old", Interpolate("%(prop:abi_base_file)s"),
            "-new", resultFile,
            "-report-path", reportFile,
            "-skip-internal", ".*UMatData.*|.*randGaussMixture.*|.*cv.*hal.*(Filter2D|Morph|SepFilter2D).*|" + \
                "_ZN2cv3ocl7ProgramC1ERKNS_6StringE|_ZN2cv3ocl7ProgramC2ERKNS_6StringE|" + \
                ".*experimental_.*",
        ]
        ShellCommand.__init__(self, workdir='build', command=cmd, logfiles={"report": reportFile}, **kwargs)


    def describe(self, done=False):
        if done:
            try:
                t = self.getLog("stdio").getText()
            except:
                return ["no log"]
            result = []
            for word in ["Binary", "Source"]:
                pattern = 'total.*%s.*problems: (\d+), warnings: (\d+)' % word
                m = re.search(pattern, t)
                if m:
                    result.append(word)
                    result.append("%s/%s" % m.group(1, 2))
            return result
        else:
            return ["compare", "ABI dumps"]


    def createSummary(self, log):
        ShellCommand.createSummary(self, log)
        self.addHTMLLog ('report-html', self.getLog("report").getText())



class LinuxPrecommitFactory(BaseFactory):

    def __init__(self, *args, **kwargs):
        myargs = dict(
            branch='branch', isPrecommit=True, platform='default',
            osType=OSType.LINUX, is64=True, useIPP='ICV')
        myargs.update(kwargs)
        BaseFactory.__init__(self, *args, **myargs)


    def initConstants(self):
        BaseFactory.initConstants(self)
        self.installPath = '../install'


    def set_cmake_parameters(self):
        BaseFactory.set_cmake_parameters(self)
        if not isBranch24(self):
            self.cmakepars['GENERATE_ABI_DESCRIPTOR'] = 'ON'
        self.cmakepars['CMAKE_INSTALL_PREFIX'] = self.installPath


    @defer.inlineCallbacks
    def build(self):
        yield BaseFactory.cmake(self)
        yield BaseFactory.compile(self, config='debug' if self.isDebug else 'release', target='install')
        if isNotBranch24(self):
            yield self.check_build()
            if not self.isContrib:
                if bool(self.getProperty('ci-run_abi_check', default=True)):
                    yield self.check_abi()


    @defer.inlineCallbacks
    def check_build(self):
        d = 'samples_build'
        cmake_command = self.envCmd.split() + [
            'cmake',
            '../' + self.SRC_OPENCV + '/samples',
            '-DCMAKE_PREFIX_PATH=%(prop:workdir)s/build/' + self.installPath]
        if self.cmake_generator:
            cmake_command.append('-G%s' % self.cmake_generator)
        cmakedesc = 'Test cmake'
        step = \
            RemoveDirectory(dir=d, hideStepIf=lambda result, s: result == SUCCESS,
                haltOnFailure=True)
        yield self.processStep(step)
        step = \
            MakeDirectory(dir=d, hideStepIf=lambda result, s: result == SUCCESS,
                haltOnFailure=True)
        yield self.processStep(step)
        step = \
            Compile(
                command=Interpolate(' '.join(cmake_command)),
                workdir=d,
                env=self.env,
                name=cmakedesc, descriptionDone=cmakedesc, description=cmakedesc,
                warningPattern=self.r_warning_pattern,
                haltOnFailure=True, warnOnWarnings=True)
        yield self.processStep(step)
        yield self.compile(
            builddir = d,
            config = 'debug' if self.isDebug else 'release',
            target = None,
            desc="Test build")


    @defer.inlineCallbacks
    def check_abi(self):
        if self.isDebug:
            return
        resultFile = 'current.abi.tar.gz'
        step = \
            AbiDumpCommand(
                builder = self,
                name = 'Generate ABI dump',
                installPath = self.installPath,
                resultFile=resultFile)
        yield self.processStep(step)
        step = \
            AbiFindBaseCommand(
                builder = self,
                name='Find ABI base file')
        yield self.processStep(step)
        step = \
            AbiCompareCommand(
                builder = self,
                name = 'Compare ABI dumps',
                resultFile=resultFile)
        yield self.processStep(step)
