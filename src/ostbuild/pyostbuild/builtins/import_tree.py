# vim: et:ts=4:sw=4
# Copyright (C) 2012-2013 Pier Luigi Fiorini <pierluigi.fiorini@gmail.com>
# Copyright (C) 2011-2012 Colin Walters <walters@verbum.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os,sys,stat,subprocess,tempfile,re,shutil
import argparse
from StringIO import StringIO
import json

from .. import builtins
from .. import buildutil
from ..subprocess_helpers import run_sync, run_sync_get_output

class OstbuildImportTree(builtins.Builtin):
    name = "import-tree"
    short_description = "Extract source data from tree into new prefix"

    def __init__(self):
        builtins.Builtin.__init__(self)

    def execute(self, argv):
        parser = argparse.ArgumentParser(description=self.short_description)
        parser.add_argument('--tree')
        parser.add_argument('--prefix')

        args = parser.parse_args(argv)
        self.parse_config()
        self.parse_snapshot_from_current()

        self.logger.info("Loading source from tree %r" % (self.snapshot.path, ))

        related_objects = run_sync_get_output(['ostree', '--repo='+ self.repo,
                                               'show', '--print-related',
                                               self.active_branch_checksum])
        ref_to_revision = {}
        for line in StringIO(related_objects):
            line = line.strip()
            (ref, revision) = line.split(' ', 1)
            ref_to_revision[ref] = revision

        if args.prefix:
            target_prefix = args.prefix
        else:
            target_prefix = self.snapshot.data['prefix']

        (fd, tmppath) = tempfile.mkstemp(suffix='.txt', prefix='ostbuild-import-tree-')
        f = os.fdopen(fd, 'w')
        for (ref, rev) in ref_to_revision.iteritems():
            if ref.startswith('components/'):
                ref = ref[len('components/'):]
                (prefix, subref) = ref.split('/', 1)
                newref = 'components/%s/%s' % (target_prefix, subref)
            elif ref.startswith('bases/'):
                # hack
                base_key = '/' + self.snapshot.data['prefix'] + '-'
                replace_key = '/' + target_prefix + '-'
                newref = ref.replace(base_key, replace_key)
            else:
                self.logger.fatal("Unhandled ref %r; expected components/ or bases/" % (ref, ))
                
            f.write('%s %s\n' % (newref, rev))
        f.close()

        run_sync(['ostree', '--repo=' + self.repo,
                  'write-refs'], stdin=open(tmppath))

        self.snapshot.data['prefix'] = target_prefix

        run_sync(['ostbuild', 'prefix', target_prefix])
        self.prefix = target_prefix

        db = self.get_src_snapshot_db()
        (path, modified) = db.store(self.snapshot.data)
        if modified:
            self.logger.info("New source snapshot: %s" % (path, ))
        else:
            self.logger.info("Source snapshot unchanged: %s" % (path, ))

builtins.register(OstbuildImportTree)