import re

from twisted.internet import defer

from buildbot.status.results import SUCCESS
from buildbot.steps.shell import ShellCommand, SetPropertyFromCommand, Compile
from buildbot.steps.slave import RemoveDirectory, MakeDirectory
from buildbot.process.properties import Interpolate

from build_utils import OSType, isNotBranch24, isBranch24, isBranch34, valueToBool
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
            if isBranch34(builder):
                print 'ABI: fallback to 3.4.10'
                return {'abi_base_file':'/opt/build-worker/abi/dump-3.4.10.abi.tar.gz'}
            else:
                print 'ABI: fallback to 4.3.0'
                return {'abi_base_file':'/opt/build-worker/abi/dump-4.3.0.abi.tar.gz'}
        cmd = builder.envCmd + 'ls -1 /opt/build-worker/abi/*.abi.tar.gz'
        SetPropertyFromCommand.__init__(self, workdir='build', command=cmd, extract_fn=extractor, **kwargs)


    def getCandidates(self):
        verString = self.getProperty('commit-description', '3.4.10' if isBranch34(self.build) else '4.3.0')
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
        ] + (["-api"] if not isBranch34(builder) else []) + [
            "-l", "opencv",
            "-old", Interpolate("%(prop:abi_base_file)s"),
            "-new", resultFile,
            "-report-path", reportFile,
        ] + ([
            "-skip-internal", ".*UMatData.*|.*randGaussMixture.*|.*cv.*hal.*(Filter2D|Morph|SepFilter2D).*|" + \
                "_ZN2cv3ocl7ProgramC1ERKNS_6StringE|_ZN2cv3ocl7ProgramC2ERKNS_6StringE|" + \
                ".*experimental_.*" + \
                "|_ZN9_IplImageC.*|_ZN7CvMatNDC.*" + \
                "|.*2cv10AutoBuffer.*" + \
                "|_ZN2cv7MomentsC.*" + \
                "|.*Durand.*" + \
                "|_ZN[0-9]+Cv.+(C1|C2|D0|D1|D2|SE).*" + \
                "|.*2cv16TLSDataContainer.*" + \
                "|_ZN9_IplImageaSERKS_" + \
                "|_ZN7cvflann7anyimpl.*" + \
                ""
        ] if isBranch34(builder) else [
            "-skip-internal",
            "_ZN2cv11GGPUContext.*|" + \
            "_ZN2cv10GGPUKernel.*|" + \
            ".*scalar_wrapper_gpu.*|" + \
            "_ZN2cv4gapi3gpu7backendEv|" + \
            "_ZN2cv4gapi7imgproc3gpu7kernelsEv" + \
            "|.*Durand.*" + \
            "|_ZN2cv3dnn16readNetFromTorchERKNSt7__cxx1112basic_stringIcEEb" + \
            "|_ZN2cv7MatExprC.*" + \
            "|_ZN2cv4gapi7combineERKNS0_14GKernelPackageES3_NS_12unite_policyE" + \
            "|_ZNK2cv4gapi14GKernelPackage6lookupERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEERKSt6vectorINS0_8GBackendESaISB_EE" + \
            "|_ZN2cv12GIOProtoArgsINS_6In_TagEEC.*" + \
            "|_ZN2cv12GIOProtoArgsINS_7Out_TagEEC.*" + \
            "|_ZN2cv12GComputation5applyERKSt6vectorINS_3MatESaIS2_EES6_OS1_INS_11GCompileArgESaIS7_EE" + \
            "|_ZN2cv4gapi5LUT3DERKNS_4GMatERKNS_4GMatEi" + \
            "|_ZN2cv3dnn9CropLayer.*" + \
            "|.*8descr_of.*" + \
            "|.*4gapi3wip.*" + \
            "|_ZN2cv4gapi3ocv7kernelsEv" + \
            "|_ZN2cv9GCompiledclEOSt6vectorINS_4util7variantIJNS_3MatENS_7Scalar_IdEENS_4UMatENS_4gapi3own3MatENS9_6ScalarENS_6detail9VectorRefEEEESaISE_EEOS1_INS3_IJPS4_PS6_PS7_PSA_PSB_SD_EEESaISN_EE" + \
            "|_ZN2cv12GComputation5applyEOSt6vectorINS_4util7variantIJNS_3MatENS_7Scalar_IdEENS_4UMatENS_4gapi3own3MatENS9_6ScalarENS_6detail9VectorRefEEEESaISE_EEOS1_INS3_IJPS4_PS6_PS7_PSA_PSB_SD_EEESaISN_EEOS1_INS_11GCompileArgESaISR_EE" + \
            "|.*detail.*BasicVectorRef.*" + \
            "|.*detail.*tracked_cv_umat.*" + "|.*ocl_get_out.*GMat.*" + \
            "|_ZN2cv4gapi7imgproc3cpu7kernelsEv|_ZN2cv4gapi7imgproc5fluid7kernelsEv|_ZN2cv4gapi7imgproc3ocl7kernelsEv" + \
            "|.*2cv5instr.*" + \
            "|.*12GFluidKernel.*" + \
            "|_ZN9_IplImageaSERKS_" + \
            "|_ZN16CvNArrayIteratorC.*" + \
            "|_ZN2cv7MomentsC.*" + \
            "|_ZN2cv7MomentsD.*" + \
            "|_ZN7CvChain.*" + \
            "|_ZN15CvChainPtReader.*" + \
            "|_ZN15CvConnectedComp.*" + \
            "|_ZN9CvContour.*" + \
            "|_ZN11CvHistogram.*" + \
            "|_ZN12CvPoint.*" + \
            "|_ZN11CvSize.*" + \
            "|.*anon-union-types.*" + \
            "|_ZN7cvflann7anyimpl.*" + \
            ""
        ])
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
        self.run_abi_check = kwargs.pop('run_abi_check', False)
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
        if isNotBranch24(self):
            self.cmakepars['GENERATE_ABI_DESCRIPTOR'] = 'ON'
            if not isBranch34(self):
                self.cmakepars['OPENCV_ABI_SKIP_MODULES_LIST'] = 'gapi'
        self.cmakepars['CMAKE_INSTALL_PREFIX'] = self.installPath


    @defer.inlineCallbacks
    def build(self):
        yield BaseFactory.cmake(self)
        yield BaseFactory.compile(self, config='debug' if self.isDebug else 'release', target='install')
        if isNotBranch24(self):
            if valueToBool(self.getProperty('build_examples', default=self.buildExamples)):
                yield self.check_samples_standalone()
            if isNotBranch24(self) and not self.isContrib:
                if bool(self.getProperty('ci-run_abi_check', default=self.run_abi_check)):
                    yield self.check_abi()
        yield self.optional_build_gapi_standalone()


    @defer.inlineCallbacks
    def check_samples_standalone(self):
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
