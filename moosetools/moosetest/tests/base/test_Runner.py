#!/usr/bin/env python3
#* This file is part of MOOSETOOLS repository
#* https://www.github.com/idaholab/moosetools
#*
#* All rights reserved, see COPYRIGHT for full restrictions
#* https://github.com/idaholab/moosetools/blob/main/COPYRIGHT
#*
#* Licensed under LGPL 2.1, please see LICENSE for details
#* https://www.gnu.org/licenses/lgpl-2.1.html

import io
import logging
import unittest
from moosetools.parameters import InputParameters
from moosetools.base import MooseException
from moosetools import moosetest


class TestRunner(unittest.TestCase):
    def testDefault(self):

        # name is required
        with self.assertRaises(MooseException) as ex:
            runner = moosetest.base.Runner()
        self.assertIn("The parameter 'name' is marked as required", str(ex.exception))

        runner = moosetest.base.Runner(name='name')
        self.assertIsNone(runner.getParam('differs'))

        with self.assertRaises(NotImplementedError) as ex:
            runner.execute()
        self.assertIn("The 'execute' method must be overridden.", str(ex.exception))

    def testControllers(self):
        class ProxyController(object):
            @staticmethod
            def validObjectParams():
                params = InputParameters()
                params.add('platform')
                return params

            def getParam(self, value):
                return 'test'

        runner = moosetest.base.make_runner(moosetest.base.Runner, [
            ProxyController(),
        ],
                                            name='name',
                                            test_platform='TempleOS')
        self.assertIn('test', runner.parameters())
        self.assertIn('platform', runner.getParam('test'))
        self.assertEqual(runner.getParam('test_platform'), 'TempleOS')

    def testDiffers(self):
        d = moosetest.base.make_differ(moosetest.base.Differ, name='a')
        runner = moosetest.base.make_runner(moosetest.base.Runner, differs=(d, ), name='name')
        self.assertIs(runner.getParam('differs')[0], d)


if __name__ == '__main__':
    unittest.main(module=__name__, verbosity=2)
