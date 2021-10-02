import os
from build_utils import *

print "Configure builds..."

import constants
from constants import trace, PLATFORM_ANY, PLATFORM_DEFAULT, PLATFORM_SKYLAKE, PLATFORM_SKYLAKE_X

import buildbot_passwords
from buildbot.buildslave import BuildSlave

INTEL_COMPILER_TOOLSET_CURRENT=('-icc17', 'Intel C++ Compiler 17.0')
INTEL_COMPILER_DOCKER_CURRENT=('-icc17', 'ubuntu-icc:16.04')

workers = []
for worker in constants.worker:
    trace("Register worker: " + worker + " with passwd=*** and params=(%s)" % constants.worker[worker])
    workers.append(BuildSlave(worker, buildbot_passwords.worker[worker], **(constants.worker[worker])))

platforms = [
    PLATFORM_DEFAULT,
    PLATFORM_SKYLAKE_X,
]

def platformParameter(branch, **params):
    isContrib = params.get('isContrib', None)
    if branch == '2.4' or isContrib:
        return [PLATFORM_DEFAULT]
    return platforms

PlatformWindowsCompiler = {
    PLATFORM_DEFAULT: [WinCompiler.VC14], #, WinCompiler.VC15],
}

def osTypeParameter(platform, **params):
    if platform == PLATFORM_DEFAULT:
        return OSType.all
    if platform == PLATFORM_SKYLAKE_X:
        return [OSType.LINUX]
    assert False

def androidABIParameter(platform, osType, **params):
    if osType != OSType.ANDROID:
        return [None]
    if platform in ['xxxxx']:
        return [None, 'x86']
    return [None]

def androidDeviceParameter(platform, osType, **params):
    if osType != OSType.ANDROID:
        return [None]
    if platform in ['xxxxx']:
        return ['xxxxx.android:5555']
    else:
        return [None]

def androidParameters():
    return [dict(androidABI=androidABIParameter), dict(androidDevice=androidDeviceParameter)]

def is64ParameterCheck(platform, osType, **params):
    if osType == OSType.ANDROID:
        return [None]
    if platform == PLATFORM_SKYLAKE_X:
        return [True]
    if platform in ['xxxxx']:
        return [False]
    if osType == OSType.WINDOWS:
        return [True, False]
    if osType == OSType.LINUX:
        return [True, False]
    if osType == OSType.MACOSX:
        return [None]
    return [True]

def availableCompilers(platform, osType, **params):
    if osType == OSType.ANDROID:
        return [None]
    if osType == OSType.WINDOWS:
        return PlatformWindowsCompiler[platform]
    else:
        return [None]

def availableToolset(platform, osType, **params):
    if osType == OSType.WINDOWS:
        return [None] #, INTEL_COMPILER_TOOLSET_CURRENT]
    else:
        return [None]

def useIPPParameter(branch, platform, osType, compiler, **params):
    androidABI = params.get('androidABI', None)
    if androidABI == 'x86':
        res = [False, 'ICV']
    elif osType == OSType.ANDROID:
        return [None]
    elif osType == OSType.MACOSX:
        res = [False, 'ICV']
    elif osType == OSType.WINDOWS:
        res = [False, 'ICV']
    else:
        res = [False, 'ICV']
    if branch.startswith('2.4'):
        res = list(set([False, None]) & set(res))
    return res

def useSSEParameter(branch, platform, osType, compiler, useIPP, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [None]
    is64 = params.get('is64', True)
    if useIPP != False:
        return [None]
    if not branch.startswith('2.4') and platform != PLATFORM_DEFAULT:
        return [False]
    if osType == OSType.WINDOWS and compiler == PlatformWindowsCompiler[platform][-1] and is64:
        return [None, False]
    if platform == PLATFORM_DEFAULT and osType == OSType.LINUX and is64:
        return [None, False]
    return [None]

def useOpenCLParameter(platform, osType, compiler, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [True, False]
    is64 = params.get('is64', None)
    useSSE = params.get('useSSE', None)
    if osType == OSType.ANDROID:
        return [False]
    if useSSE == False:
        return [False]
    if osType == OSType.WINDOWS:
        if compiler == PlatformWindowsCompiler[platform][-1]:
            if platform == PLATFORM_DEFAULT:
                return [True, False]
            else:
                return [True]
    if osType == OSType.MACOSX:
        return [True, False]
    if osType == OSType.LINUX:
        return [False] if is64 is False else [True, False]
    return [False]

def testOpenCLParameter(platform, osType, compiler, useOpenCL, **params):
#    if osType == OSType.MACOSX:
#        return [False]
    return [useOpenCL]

def useDebugParameter(platform, osType, compiler, useIPP, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [None]
    useSSE = params.get('useSSE', None)
    if useSSE != False or platform != PLATFORM_DEFAULT:
        return [None]
    return [None, True]

def useShared(branch, platform, osType, useIPP, **params):
    if platform == PLATFORM_SKYLAKE_X:
        return [True]
    is64 = params.get('is64', None)
    compiler = params.get('compiler', None)
    isDebug = params.get('isDebug', None)
    enableStatic = False
    if branch == 'next' and osType == OSType.WINDOWS:
        return [True]  # without static builds
    if platform == PLATFORM_DEFAULT and compiler == WinCompiler.VC15:
        return [True] # without static builds
    if platform == PLATFORM_DEFAULT and not is64 == False and not osType == OSType.ANDROID and not isDebug:
        enableStatic = True
    if not branch.startswith('2.4') and useIPP != 'ICV':
        enableStatic = False
    return [True, False] if enableStatic else [True]

def buildExamplesParameter(buildShared, **params):
    if buildShared is False:
        return [False]
    return [True]

def availableDockerImage(platform, osType, testOpenCL, **params):
    if osType == OSType.LINUX:
        if platform == PLATFORM_SKYLAKE_X and testOpenCL:
            return [(None, 'ubuntu:16.04')]
        return [None] #, INTEL_COMPILER_DOCKER_CURRENT]
    else:
        return [None]


from factory_builders_aggregator import *
from factory_helpers import *
import factory_ocl
import factory_docs
from factory_android import AndroidPackFactory
from factory_arm import ARMv7Factory, ARMv8Factory
from factory_ios import iOSFactory
from factory_linux import LinuxPrecommitFactory
from factory_valgrind import ValgrindFactory
from factory_coverage import CoverageFactory
from factory_winpack import WinPackBuild, WinPackBindings, WinPackDocs, WinPackTest, WinPackController, WinPackCreate, WinPackUpload

# Current "top-level" factory
OpenCVBuildFactory = factory_ocl.OCL_factory

builders = []
schedulers = []

def addConfiguration(descriptor):
    global builders, schedulers
    (new_builders, new_schedulers) = descriptor.Register()
    builders = builders + new_builders
    schedulers = schedulers + new_schedulers

# Nightly builders
for branch in ['2.4', '3.4', 'master', 'next']:
    genNightly = True
    if branch == 'master':
        nightlyMinute = 0
        dayOfWeek=6
        cvVersion = 4
    if branch == 'next':
        nightlyMinute = 10
        dayOfWeek=6
        cvVersion = 5
    if branch == '3.4':
        nightlyMinute = 5
        dayOfWeek=5
        cvVersion = 3
    if branch == '2.4':
        nightlyMinute = 10
        dayOfWeek=5
        genNightly = False
        cvVersion = 2
    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='check-',
            genForce=True, genNightly=genNightly, nightlyHour=23, nightlyMinute=nightlyMinute,
            builders=[
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly']),
                    variate=[
                        dict(platform=platformParameter),
                        dict(osType=osTypeParameter),
                    ] + androidParameters() + [
                        dict(is64=is64ParameterCheck),
                        dict(compiler=availableCompilers),
                        dict(cmake_toolset=availableToolset),
                        dict(useIPP=useIPPParameter),
                        dict(useSSE=useSSEParameter),
                        dict(useOpenCL=useOpenCLParameter),
                        dict(testOpenCL=testOpenCLParameter),
                        dict(isDebug=useDebugParameter),
                        dict(buildShared=useShared),
                        dict(buildExamples=buildExamplesParameter),
                        dict(dockerImage=availableDockerImage),
                    ]
                ),
                SetOfBuilders(
                    factory_class=factory_docs.Docs_factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'docs'], platform=PLATFORM_DEFAULT,
                                     useSlave=['linux-1','linux-2','linux-4'] if branch != '2.4' else ['linux-1'],
                                     osType=OSType.LINUX)
                ),
            ] + ([
                SetOfBuilders(
                    factory_class=iOSFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'ios_pack'], platform=PLATFORM_DEFAULT)
                ),
                SetOfBuilders(
                    factory_class=ARMv7Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT,
                                     useSlave=['linux-1','linux-2','linux-4']
                                )
                ),
                SetOfBuilders(
                    factory_class=CoverageFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'coverage'], platform=PLATFORM_ANY,
                                     osType=OSType.LINUX, isDebug=True, useName='coverage',
                                     useSlave=['linux-1']
                                )
                ),
                SetOfBuilders(
                    factory_class=AndroidPackFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'android_pack'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.ANDROID, is64=True, useName='pack',
                                     useSlave=['linux-4', 'linux-6'],
                    )
                ),
                SetOfBuilders(
                    factory_class=ARMv8Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT,
                                     useSlave=['linux-1','linux-2','linux-4'])
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'powerpc'], useName='powerpc-64le', dockerImage='powerpc64le',
                                     useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'])
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'mips'], useName='mips-msa', dockerImage='mips64el',
                                     useSlave=['linux-1'])
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'js'], useName='javascript-emscripten', dockerImage='javascript',
                                     useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'])
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'js'], useName='javascript-simd-emscripten', dockerImage='javascript-simd',
                                     useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'])
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'skl'], platform=PLATFORM_SKYLAKE,
                        useName='openvino', dockerImage='ubuntu-openvino-2021.4.1:20.04',
                        builder_properties={'modules_filter':'dnn,python2,python3,java,gapi', 'parallel_tests': 1}
                    )),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'skl', 'opencl'], platform=PLATFORM_SKYLAKE,
                        useName='openvino-opencl', dockerImage='ubuntu-openvino-2021.4.1:20.04',
                        builder_properties={'modules_filter':'dnn,python2,python3,java,gapi', 'parallel_tests': 1, 'test_filter': '*YOLO*:*VINO*:*Infer*:*Layer*:*layer*'},
                        #schedulerNightly=False,
                        useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'skx'], platform=PLATFORM_SKYLAKE_X,
                        useName='openvino', dockerImage='ubuntu-openvino-2021.4.1:20.04',
                        builder_properties={'modules_filter':'dnn,python2,python3,java,gapi', 'parallel_tests': 1},
                        useSlave=['linux-3','linux-5'])),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'skx', 'opencl'], platform=PLATFORM_SKYLAKE_X,
                        useName='openvino-opencl', dockerImage='ubuntu-openvino-2021.4.1:20.04',
                        builder_properties={'modules_filter':'dnn,python2,python3,java,gapi', 'parallel_tests': 1},
                        useSlave=['linux-3','linux-5'], useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'mac'],
                        osType=OSType.MACOSX, platform=PLATFORM_DEFAULT,
                        useName='openvino', buildImage='openvino-2021.4.1',
                        builder_properties={'modules_filter':'dnn,python2,python3,java,gapi', 'parallel_tests': 1},
                        useSlave=['macosx-1'])),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        useName='openvino', buildImage='openvino-2021.4.1', is64=True, compiler=None, useOpenCL=True, testOpenCL=False,
                        builder_properties={
                            'modules_filter':'dnn,python2,python3,java,gapi',
                            'parallel_tests': 1
                        },
                        useSlave=['windows-1'])),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'openvino', 'windows', 'opencl'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        useName='openvino-opencl', buildImage='openvino-2021.4.1', is64=True, compiler=None, useOpenCL=True, testOpenCL=True,
                        #schedulerNightly=False,
                        builder_properties={
                            'modules_filter':'dnn,python2,python3,java,gapi',
                            #'test_filter': '*YOLO*:*VINO*:*Infer*:*Layer*:*layer*',
                            'parallel_tests': 1,
                            'test_maxtime': 2*60*60,
                        },
                        useSlave=['windows-3'])),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_SKYLAKE)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'skl', 'ubuntu18', 'avx2', 'ninja'],
                        useName='opt-avx2', dockerImage='ubuntu:18.04', cmake_generator='Ninja',
                        cmake_parameters={'CPU_BASELINE': 'AVX2', 'CPU_DISPATCH': ''},
                        useIPP=False, useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_SKYLAKE)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'skl', 'ubuntu18', 'avx', 'ninja'],
                        useName='opt-avx', dockerImage='ubuntu:18.04', cmake_generator='Ninja',
                        cmake_parameters={'CPU_BASELINE': 'AVX', 'CPU_DISPATCH': ''},
                        useIPP=False, useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_SKYLAKE)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'skl', 'ubuntu18', 'sse42', 'ninja'],
                        useName='opt-sse42', dockerImage='ubuntu:18.04', cmake_generator='Ninja',
                        cmake_parameters={'CPU_BASELINE': 'SSE4_2', 'CPU_DISPATCH': ''},
                        useIPP=False, useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_SKYLAKE_X)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'skx', 'ubuntu18', 'avx512', 'ninja'],
                        useName='opt-avx512', dockerImage='ubuntu:18.04', cmake_generator='Ninja',
                        cmake_parameters={'CPU_BASELINE': 'AVX512_SKX', 'CPU_DISPATCH': ''},
                        useIPP=False, useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_SKYLAKE)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'skl', 'ubuntu18', 'avx2', 'clang', 'ninja'],
                        useName='opt-avx2', compiler='clang', dockerImage='ubuntu-clang:18.04', cmake_generator='Ninja',
                        cmake_parameters={'CPU_BASELINE': 'AVX2', 'CPU_DISPATCH': ''},
                        useIPP=False, useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'ubuntu18', 'clang', 'ninja'],
                        compiler='clang', dockerImage='ubuntu-clang:18.04', cmake_generator='Ninja',
                        useSlave=['linux-1','linux-2','linux-4'],
                        useIPP=False, useOpenCL=True, testOpenCL=True)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'qt', 'openmp', 'ninja'],
                        useName='etc-qt-openmp', dockerImage='qt:16.04', cmake_generator='Ninja',
                        cmake_parameters={'WITH_OPENMP': 'ON'},
                        useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'],
                        useOpenCL=True, testOpenCL=False)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'fedora', 'tbb', 'ninja'],
                        useName='etc-fedora-tbb', dockerImage='fedora:28', cmake_generator='Ninja',
                        cmake_parameters={'WITH_TBB': 'ON'},
                        useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'],
                        useOpenCL=True, testOpenCL=False)),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'ffmpeg', 'ninja'],
                        useName='etc-ffmpeg-master', dockerImage='ffmpeg-master', cmake_generator='Ninja',
                        cmake_parameters={'WITH_GSTREAMER': 'OFF'},  # avoid loading of system FFmpeg libraries via GStreamer libav plugin
                        builder_properties={'modules_filter':'videoio,video,tracking'},
                        useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'],
                        useOpenCL=False, testOpenCL=False)),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildImage='msvs2017', is64=True, compiler=WinCompiler.VC15,
                        useOpenCL=True, testOpenCL=True,
                        useSlave=['windows-1']
                    )),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildImage='msvs2017-win32', is64=False, compiler=WinCompiler.VC15,
                        useOpenCL=True, testOpenCL=True,
                        useSlave=['windows-1']
                    )),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildImage='msvs2019', is64=True, compiler=WinCompiler.VC16,
                        useOpenCL=True, testOpenCL=True,
                        useSlave=['windows-1', 'windows-2']
                    )),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildImage='msvs2019-win32', is64=False, compiler=WinCompiler.VC16,
                        useOpenCL=True, testOpenCL=True,
                        useSlave=['windows-1', 'windows-2']
                    )),
            ] if cvVersion > 2 else []) + ([
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'vulkan'],
                        useName='vulkan', dockerImage='ubuntu-vulkan:16.04',
                        builder_properties={'modules_filter':'dnn,python2,python3,java', 'parallel_tests': 1},
                        useSlave=['linux-4', 'linux-6'], useOpenCL=True, testOpenCL=True,
                    )
                ),
            ] if cvVersion >= 4 else []) + ([
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'cuda'], useName='cuda',
                    dockerImage='ubuntu-cuda:16.04', useSlave=['linux-4', 'linux-6'])),
            ] if cvVersion == 3 else []) + ([
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildImage='msvs2019', is64=True, compiler=WinCompiler.VC16, buildShared=False,
                        useOpenCL=True, testOpenCL=True,
                        useSlave=['windows-1', 'windows-2']
                    )
                ),
            ] if cvVersion >= 5 else [])
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(
            branch=branch, nameprefix='weekly-',
            genForce=True, genNightly=genNightly, nightlyHour=4, nightlyMinute=nightlyMinute, dayOfWeek=dayOfWeek,
            builders=([
                SetOfBuilders(
                    factory_class=iOSFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'ios_pack'], platform=PLATFORM_DEFAULT)
                ),
                SetOfBuilders(
                    factory_class=ARMv7Factory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'arm'], platform=PLATFORM_DEFAULT,
                                     useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']
                    )
                ),
                SetOfBuilders(
                    factory_class=CoverageFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'coverage'], platform=PLATFORM_ANY,
                                     osType=OSType.LINUX, isDebug=True, useName='coverage',
                                     useSlave=['linux-1']
                    )
                ),
                SetOfBuilders(
                    factory_class=AndroidPackFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'android_pack'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.ANDROID, is64=True, useName='pack',
                                     useSlave=['linux-4', 'linux-6'],
                    )
                ),
            ] if branch == '2.4' else []) + [
                SetOfBuilders(
                    factory_class=ValgrindFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'valgrind'], platform=PLATFORM_DEFAULT,
                                     osType=OSType.LINUX, isDebug=True, useName='valgrind',
                                     useSlave=['linux-2']
                    )
                ),
            ] + ([
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(
                        branch=branch, buildWithContrib=False, tags=['weekly', 'etc'],
                        useName='etc-simd-emulator', buildImage='simd-emulator',
                        useSlave=['linux-1']
                    )
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(
                        branch=branch, buildWithContrib=False, tags=['weekly', 'etc'],
                        useName='etc-centos', buildImage='centos:7',
                        useSlave=['linux-1']
                    )
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                    init_params=dict(
                        branch=branch, isContrib=True, tags=['weekly', 'etc', 'contrib'],
                        useName='etc-centos', buildImage='centos:7',
                        useSlave=['linux-1']
                    )
                ),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(
                        branch=branch, buildWithContrib=False, tags=['weekly', 'etc', 'mac'],
                        osType=OSType.MACOSX, platform=PLATFORM_DEFAULT,
                        useName='etc-osx-framework', buildImage='osx_framework',
                        useSlave=['macosx-1']
                    )
                ),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(
                        branch=branch, isContrib=True, tags=['weekly', 'etc', 'mac', 'contrib'],
                        osType=OSType.MACOSX, platform=PLATFORM_DEFAULT,
                        useName='etc-osx-framework', buildImage='osx_framework',
                        useSlave=['macosx-1']
                    )
                ),
                SetOfBuilders(
                    factory_class=linux(platform(PLATFORM_SKYLAKE)(OpenCVBuildFactory)),
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['weekly', 'halide', 'skl', 'opencl'],
                        useName='halide', dockerImage='halide:16.04',
                        useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6'],
                        builder_properties={'modules_filter':'dnn,python2,python3,java', 'parallel_tests': 1},
                        useOpenCL=True, testOpenCL=False)
                ),
            ] if cvVersion >= 3 else []) + ([
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'windows'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildImage='msvs2019', is64=True, compiler=WinCompiler.VC16, buildShared=False,
                        useOpenCL=False,
                        useSlave=['windows-1', 'windows-2']
                    )
                ),
            ] if cvVersion >= 5 else [])
        )
    )

    if branch != '2.4':
        addConfiguration(
            SetOfBuildersWithSchedulers(branch=branch, nameprefix='checkcontrib-',
                genForce=True, genNightly=genNightly, nightlyHour=23, nightlyMinute=20 + nightlyMinute,
                builders=[
                    # OpenCV Contrib
                    SetOfBuilders(
                        factory_class=OpenCVBuildFactory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly']),
                        variate=[
                            dict(platform=platformParameter),
                            dict(osType=osTypeParameter),
                        ] + androidParameters() + [
                            dict(is64=is64ParameterCheck),
                            dict(compiler=availableCompilers),
                            dict(useOpenCL=useOpenCLParameter),
                            dict(testOpenCL=testOpenCLParameter),
                        ]
                    ),
                    SetOfBuilders(
                        factory_class=factory_docs.Docs_factory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'docs'], platform=PLATFORM_DEFAULT,
                                         osType=OSType.LINUX,
                                         useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']
                        )
                    ),
                    SetOfBuilders(
                        factory_class=ARMv7Factory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT,
                                         useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']
                        )
                    ),
                    SetOfBuilders(
                        factory_class=ARMv8Factory,
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'arm'], platform=PLATFORM_DEFAULT,
                                         useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']
                        )
                    ),
                ] + ([
                    SetOfBuilders(
                        factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                        init_params=dict(isContrib=True, branch=branch, tags=['nightly', 'cuda'], useName='cuda', dockerImage='ubuntu-cuda:18.04',
                                         useSlave=['linux-4', 'linux-6'])
                    ),
                ] if cvVersion >= 4 else [])
            )
        )
        addConfiguration(
            SetOfBuildersWithSchedulers(
                branch=branch, nameprefix='weekly-contrib-',
                genForce=True, genNightly=genNightly, nightlyHour=4, nightlyMinute=20 + nightlyMinute, dayOfWeek=dayOfWeek,
                builders=([
                    SetOfBuilders(
                        factory_class=ValgrindFactory,
                        init_params=dict(
                            branch=branch, isContrib=True, tags=['weekly', 'valgrind', 'contrib'], platform=PLATFORM_DEFAULT,
                            osType=OSType.LINUX, isDebug=True, useName='valgrind',
                            useSlave=['linux-2']
                        )
                    ),
                    SetOfBuilders(
                        factory_class=CoverageFactory,
                        init_params=dict(
                            branch=branch, isContrib=True, tags=['weekly', 'coverage', 'contrib'], platform=PLATFORM_DEFAULT,
                            osType=OSType.LINUX, isDebug=True, useName='coverage',
                            useSlave=['linux-1']
                        )
                    ),
                    SetOfBuilders(
                        factory_class=linux(platform(PLATFORM_ANY)(OpenCVBuildFactory)),
                        init_params=dict(
                            branch=branch, isContrib=True, tags=['weekly', 'etc', 'contrib'],
                            useName='etc-simd-emulator', buildImage='simd-emulator',
                            useSlave=['linux-1']
                        )
                    ),
                    SetOfBuilders(
                        factory_class=AndroidPackFactory,
                        init_params=dict(
                            branch=branch, isContrib=True, tags=['weekly', 'android_pack', 'contrib'], platform=PLATFORM_DEFAULT,
                            osType=OSType.ANDROID, is64=True, useName='pack-contrib',
                            useSlave=['linux-4', 'linux-6'],
                        )
                    ),
                    SetOfBuilders(
                        factory_class=iOSFactory,
                        init_params=dict(
                            branch=branch, isContrib=True, tags=['weekly', 'ios_pack'], platform=PLATFORM_DEFAULT
                        )
                    ),
                ])
            )
        )


    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='winpackbuild-',
            genTrigger=True, genForce=True,
            builders=[
                SetOfBuilders(
                    factory_class=WinPackBuild,
                    init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT),
                    variate=[
                        dict(buildShared=[True, False] if branch == '2.4' else [True]),
                        dict(is64=[True, False] if branch == '2.4' else [True]),
                        dict(compiler=['vc16'] if cvVersion >= 5 else (['vc14'] if branch == '2.4' else ['vc14', 'vc15'])),
                    ]
                ),
                SetOfBuilders(
                    factory_class=WinPackBindings,
                    init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT, buildShared=False),
                    variate=[
                        dict(is64=[True] if cvVersion >= 5 else [True, False]),
                        dict(compiler=['vc16'] if cvVersion >= 5 else ['vc14']),
                    ]
                )
            ] +
            ([
                SetOfBuilders(
                    factory_class=WinPackDocs,
                    init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.LINUX, platform=PLATFORM_DEFAULT, is64=True),
                    variate=[],
                ),
            ] if branch == '2.4' else [])
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(nameprefix='winpack-', branch=branch,
            genForce=True, genNightly=genNightly, nightlyHour=3 if branch == '2.4' else 0, nightlyMinute=nightlyMinute, dayOfWeek = 6 if branch == '2.4' else '*',
            builders=[
                SetOfBuilders(
                    factory_class=WinPackController,
                    init_params=dict(
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        buildTriggerName='winpackbuild-trigger_' + branch,
                        createTriggerName='winpackcreate-trigger_' + branch,
                        branch=branch, tags=['pack-' + branch])
                ),
            ] + ([] if branch == '2.4' else [
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'dldt', 'windows', 'pack-' + branch],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        useName='winpack_dldt-build', buildImage='winpack-dldt',
                        is64=True, compiler=None, useOpenCL=True, testOpenCL=False,
                        useSlave=['windows-1'])),
                SetOfBuilders(
                    factory_class=OpenCVBuildFactory,
                    init_params=dict(branch=branch, buildWithContrib=False, tags=['nightly', 'dldt', 'windows', 'pack-' + branch, 'debug'],
                        osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        useName='winpack_dldt-build', buildImage='winpack-dldt-debug', isDebug=True,
                        is64=True, compiler=None, useOpenCL=True, testOpenCL=False,
                        useSlave=['windows-1'])),
            ])
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(nameprefix='winpackcreate-', branch=branch,
            genForce=True, genTrigger=True,
            builders=
                SetOfBuilders(
                    factory_class=WinPackCreate,
                    init_params=dict(osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                        testsTriggerName='winpacktests-trigger_' + branch,
                        completionTriggerName='winpackupload-trigger_' + branch,
                        branch=branch, tags=['pack-' + branch])
                ),
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(branch=branch, nameprefix='winpacktests-',
            genTrigger=True,
            builders=SetOfBuilders(
                factory_class=WinPackTest,
                init_params=dict(branch=branch, tags=['pack-' + branch], osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT),
                variate=[
                    dict(buildShared=[True, False]),
                    dict(is64=[True, False] if branch == '2.4' else [True]),
                    dict(compiler=['vc16'] if cvVersion >= 5 else (['vc14'] if branch == '2.4' else ['vc14', 'vc15'])),
                ]
            )
        )
    )
    addConfiguration(
        SetOfBuildersWithSchedulers(nameprefix='winpackupload-', branch=branch,
            genForce=True, genTrigger=True,
            builders=SetOfBuilders(
                factory_class=WinPackUpload,
                init_params=dict(
                    osType=OSType.WINDOWS, platform=PLATFORM_DEFAULT,
                    branch=branch, tags=['pack-' + branch],
                    #perfTestsTriggerName='perftests-trigger_' + branch,
                )
            )
        )
    )

    #addConfiguration(
    #    SetOfBuildersWithSchedulers(branch=branch, nameprefix='perftests-',
    #        genForce=True, genTrigger=True,
    #        builders=[]
    #    )
    #)

# end: for branch in [...]


precommitFactory = precommit(platform(PLATFORM_DEFAULT)(OpenCVBuildFactory))
precommitFactory = IPP_ICV(precommitFactory)
LinuxPrecommit = precommit(platform(PLATFORM_ANY)(LinuxPrecommitFactory))
WindowsPrecommit64 = windows(precommitFactory)
WindowsPrecommit32 = windows32(precommitFactory)
MacOSXPrecommit = macosx(OpenCL_noTest(precommitFactory))
AndroidPrecommit = android(precommit(platform(PLATFORM_DEFAULT)(OpenCVBuildFactory)))
OCLPrecommit = windows(OpenCL(precommitFactory))
OCLLinuxPrecommit = linux(OpenCL(platform(PLATFORM_DEFAULT)(precommitFactory)))
OCLMacPrecommit = macosx(OpenCL(precommitFactory))
LinuxPrecommitNoOpt = LinuxPrecommit
DocsPrecommit = linux(precommit(platform(PLATFORM_ANY)(factory_docs.Docs_factory)))
ARMv7Precommit = linux(precommit(platform(PLATFORM_DEFAULT)(ARMv7Factory)))
ARMv8Precommit = linux(precommit(platform(PLATFORM_DEFAULT)(ARMv8Factory)))
iOSPrecommit = precommit(platform(PLATFORM_DEFAULT)(iOSFactory))

addConfiguration(
    SetOfBuildersWithSchedulers(branch='branch', nameprefix='precommit-',
        genForce=True, genNightly=False,
        builders=[
            LinuxPrecommit(builderName='precommit_linux64', run_abi_check=True),
            linux32(LinuxPrecommit)(builderName='precommit_linux32', buildWithContrib=False),
            #LinuxPrecommit(builderName='precommit_linux64-icc', buildImage='ubuntu-icc:16.04'),
            OCLLinuxPrecommit(builderName='precommit_opencl_linux',
                    cmake_parameters={
                        'OPENCV_CXX11':'ON', 'WITH_TBB':'ON',
                        'VIDEOIO_PLUGIN_LIST':'all',
                        'PYTHON3_LIMITED_API': 'ON',
                    },
                    branchExtraConfiguration={
                        '3.4': dict(buildImage='ubuntu:16.04'),
                        'master': dict(buildImage='ubuntu:16.04'),
                        'next': dict(buildImage='ubuntu:20.04'),
                    },
            ),
            OCLLinuxPrecommit(builderName='precommit_linux64-avx2',
                    platform=PLATFORM_ANY,
                    cmake_parameters={'OPENCV_CXX11':'ON', 'CPU_BASELINE':'AVX2', 'CPU_DISPATCH':''},
                    useIPP=False,  # check OpenCV AVX2 code instead of IPP
                    builder_properties={'buildworker':'linux-1,linux-2'},
                    branchExtraConfiguration={
                        '3.4': dict(buildImage='ubuntu:18.04'),
                        'master': dict(buildImage='ubuntu:18.04'),
                        'next': dict(buildImage='ubuntu:20.04'),
                    },
            ),
            LinuxPrecommitNoOpt(builderName='precommit_linux64_no_opt',
                    useIPP=False, useSSE=False, useOpenCL=False, isDebug=True, buildWithContrib=False,
                    #builder_properties={'buildworker':'linux-3,linux-5'},
                    branchExtraConfiguration={
                        '3.4': dict(buildImage='ubuntu:16.04'),
                        'master': dict(buildImage='ubuntu:16.04'),
                        'next': dict(buildImage='ubuntu:20.04'),
                    },
            ),
            #WindowsPrecommit64(builderName='precommit_windows64-vc15', compiler=WinCompiler.VC15, cmake_parameters={'OPENCV_EXTRA_CXX_FLAGS': '/std:c++latest', 'WITH_OPENEXR': 'OFF'}),
            WindowsPrecommit64(builderName='precommit_windows64', compiler=WinCompiler.VC14),
            #WindowsPrecommit64(builderName='precommit_windows64-icc', cmake_toolset=INTEL_COMPILER_TOOLSET_CURRENT),
            OCLPrecommit(builderName='precommit_opencl',
                    compiler=WinCompiler.VC14,  # see branchExtraConfiguration
                    cmake_parameters={
                        #'XWITH_TBB':'ON', 'XBUILD_TBB':'ON',
                        'VIDEOIO_PLUGIN_LIST':'all',
                        'PYTHON3_LIMITED_API': 'ON',
                    },
                    branchExtraConfiguration={
                        '3.4': dict(compiler=WinCompiler.VC14),
                        'master': dict(compiler=WinCompiler.VC16),
                        'next': dict(compiler=WinCompiler.VC16),
                    },
                    useSlave=['windows-1', 'windows-2', 'windows-3'],
                    builder_properties={'buildworker': 'windows-1,windows-2'}
            ),
            #OCLPrecommit(builderName='precommit_opencl-vc15', compiler=WinCompiler.VC15),
            WindowsPrecommit32(builderName='precommit_windows32',
                    cmake_parameters={
                        'VIDEOIO_PLUGIN_LIST':'all',
                    },
            ),
            MacOSXPrecommit(builderName='precommit_macosx',
                    cmake_parameters={
                        'VIDEOIO_PLUGIN_LIST':'all',
                        'PYTHON3_LIMITED_API': 'ON',
                    },
            ),
            OCLMacPrecommit(builderName='precommit_opencl_macosx'),
            iOSPrecommit(builderName='precommit_ios', tags=['ios_pack']),
            AndroidPrecommit(builderName='precommit_android',
                    useSlave=['linux-4', 'linux-6'],
                    builder_properties={'buildworker':'linux-4,linux-6'}),
            ARMv7Precommit(builderName='precommit_armv7', tags=['arm'], useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']),
            ARMv8Precommit(builderName='precommit_armv8', tags=['arm'], useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']),
            DocsPrecommit(builderName='precommit_docs', tags=['docs'], useSlave=['linux-1',  'linux-2', 'linux-3', 'linux-4', 'linux-5', 'linux-6']),
            precommit(platform(PLATFORM_DEFAULT)(AndroidPackFactory))(builderName='precommit_pack_android', buildWithContrib=False, tags=['android_pack'],
                    useSlave=['linux-4', 'linux-6'],
            ),
            precommit(platform(PLATFORM_ANY)(LinuxPrecommitFactory))(builderName='precommit_custom_linux',
                    useIPP=None, buildImage='is_not_set_but_required'
            ),
            windows(precommitFactory)(builderName='precommit_custom_windows',
                    compiler=WinCompiler.VC15,
                    #cmake_parameters={'OPENCV_EXTRA_CXX_FLAGS': '/std:c++latest', 'WITH_OPENEXR': 'OFF'},
                    useSlave=['windows-1', 'windows-2', 'windows-3'],
                    builder_properties={'buildworker': 'windows-1'}
            ),
            macosx(precommitFactory)(builderName='precommit_custom_mac',
                    useSlave=['macosx-1', 'macosx-2'],
                    builder_properties={'buildworker': 'macosx-1'}
            ),

            contrib(LinuxPrecommit)(builderName='precommit-contrib_linux64',
                    cmake_parameters={
                        'PYTHON3_LIMITED_API': 'ON',
                    },
            ),
            #contrib(LinuxPrecommit)(builderName='precommit-contrib_linux64-icc', buildImage='ubuntu-icc:16.04'),
            contrib(OCLLinuxPrecommit)(builderName='precommit-contrib_opencl_linux',
                    buildImage='ubuntu:16.04',  # TODO 20.04
            ),
            contrib(LinuxPrecommitNoOpt)(builderName='precommit-contrib_linux64_no_opt',
                    buildImage='ubuntu:16.04',
                    useIPP=False, useSSE=False, useOpenCL=False, isDebug=True
            ),
            contrib(WindowsPrecommit64)(builderName='precommit-contrib_windows64',
                    compiler=WinCompiler.VC14,
                    branchExtraConfiguration={
                        '3.4': dict(compiler=WinCompiler.VC14),
                        'master': dict(compiler=WinCompiler.VC14),
                        'next': dict(compiler=WinCompiler.VC16),
                    },
            ),
            #contrib(WindowsPrecommit64)(builderName='precommit-contrib_windows64-icc', cmake_toolset=INTEL_COMPILER_TOOLSET_CURRENT),
            contrib(OCLPrecommit)(builderName='precommit-contrib_opencl',
                    branchExtraConfiguration={
                        '3.4': dict(compiler=WinCompiler.VC14),
                        'master': dict(compiler=WinCompiler.VC14),
                        'next': dict(compiler=WinCompiler.VC16),
                    },
            ),
            contrib(WindowsPrecommit32)(builderName='precommit-contrib_windows32'),
            contrib(MacOSXPrecommit)(builderName='precommit-contrib_macosx'),
            contrib(OCLMacPrecommit)(builderName='precommit-contrib_opencl_macosx'),
            contrib(iOSPrecommit)(builderName='precommit-contrib_ios', tags=['ios_pack']),
            contrib(AndroidPrecommit)(builderName='precommit-contrib_android',
                    useSlave=['linux-4', 'linux-6'],
            ),
            contrib(ARMv7Precommit)(builderName='precommit-contrib_armv7', tags=['arm'], useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']),
            contrib(ARMv8Precommit)(builderName='precommit-contrib_armv8', tags=['arm'], useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']),
            contrib(DocsPrecommit)(builderName='precommit-contrib_docs', tags=['docs'], useSlave=['linux-1', 'linux-2', 'linux-4', 'linux-6']),
            contrib(precommit(platform(PLATFORM_DEFAULT)(AndroidPackFactory)))(builderName='precommit-contrib_pack_android', tags=['android_pack'],
                    useSlave=['linux-4', 'linux-6'],
            ),
            contrib(LinuxPrecommit)(builderName='precommit-contrib_custom_linux64', buildImage='is_not_set_but_required'),
        ]
    )
)

print "Configure builds... DONE"
