# helper decorators
from build_utils import OSType

def platform(platform='default'):
    def _(cls):
        def _(*args, **kwargs):
            if not 'platform' in kwargs:
                kwargs['platform'] = platform
            return cls(*args, **kwargs)
        return _
    return _

def precommit(cls):
    def _(*args, **kwargs):
        kwargs['branch'] = 'branch'
        kwargs['isPrecommit'] = True
        return cls(*args, **kwargs)
    return _

def contrib(cls):
    def _(*args, **kwargs):
        kwargs['isContrib'] = True
        return cls(*args, **kwargs)
    return _

def linux(cls):
    def _(*args, **kwargs):
        kwargs['osType'] = OSType.LINUX
        kwargs['is64'] = True
        return cls(*args, **kwargs)
    return _

def windows32(cls):
    def _(*args, **kwargs):
        kwargs['osType'] = OSType.WINDOWS
        kwargs['is64'] = False
        return cls(*args, **kwargs)
    return _

def windows(cls):
    def _(*args, **kwargs):
        kwargs['osType'] = OSType.WINDOWS
        kwargs['is64'] = True
        return cls(*args, **kwargs)
    return _

def macosx(cls):
    def _(*args, **kwargs):
        kwargs['osType'] = OSType.MACOSX
        kwargs['is64'] = True
        return cls(*args, **kwargs)
    return _

def android(cls):
    def _(*args, **kwargs):
        kwargs['osType'] = OSType.ANDROID
        kwargs['useOpenCL'] = False
        return cls(*args, **kwargs)
    return _

def OpenCL(cls):
    def _(*args, **kwargs):
        kwargs['useOpenCL'] = True
        return cls(*args, **kwargs)
    return _

def OpenCL_noTest(cls):
    def _(*args, **kwargs):
        kwargs['useOpenCL'] = True
        kwargs['testOpenCL'] = False
        return cls(*args, **kwargs)
    return _

def IPP_ICV(cls):
    def _(*args, **kwargs):
        kwargs['useIPP'] = 'ICV'
        return cls(*args, **kwargs)
    return _

def IPP_None(cls):
    def _(*args, **kwargs):
        kwargs['useIPP'] = False
        return cls(*args, **kwargs)
    return _

def docs():
    def _(cls):
        def _(*args, **kwargs):
            kwargs['useIPP'] = 'ICV'
            return cls(*args, **kwargs)
        return cls
    return _
