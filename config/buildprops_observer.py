import re
from buildbot.process.buildstep import LogLineObserver
from buildbot.util import json

class BuildPropertiesObserver(LogLineObserver):

    pattern_prop = re.compile(r'(^|\n|\r)BUILD-PROP (?P<name>[^=]+)=?(?P<value>[^\r\n]*)?(\r|\n|$)')

    def __init__(self, build):
        LogLineObserver.__init__(self)
        self.target_build = build

    def errLineReceived(self, line):
        line = line.strip()
        m = self.pattern_prop.match(line)
        if m:
            name = m.group('name')
            value = m.group('value')
            if name is not None:
                if value is not None:
                    print("Set property: '%s'='%s'" % (name, value))
                    self.target_build.setProperty('ci-' + name, json.loads(value), "Runtime property", runtime=True)
                else:
                    print("Reset property: '%s'" % (name))
                    self.target_build.setProperty('ci-' + name, None, "Runtime property", runtime=True)
