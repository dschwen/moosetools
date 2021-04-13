#* This file is part of the MOOSE framework
#* https://www.mooseframework.org
#*
#* All rights reserved, see COPYRIGHT for full restrictions
#* https://github.com/idaholab/moose/blob/master/COPYRIGHT
#*
#* Licensed under LGPL 2.1, please see LICENSE for details
#* https://www.gnu.org/licenses/lgpl-2.1.html

from moosetools.moosetest.schedulers.Scheduler import Scheduler
from moosetools.moosetest import util

class RunParallel(Scheduler):
    """
    RunParallel is a Scheduler plugin responsible for executing a tester
    command and doing something with its output.
    """
    @staticmethod
    def validParams():
        params = Scheduler.validParams()
        return params

    def __init__(self, harness, *args, **kwargs):
        Scheduler.__init__(self, harness, *args, **kwargs)

    def run(self, job):
        """ Run a tester command """
        tester = job.getTester()

        # Do not execute app, and do not processResults
        if self.options.dry_run:
            self.setSuccessfulMessage(tester)
            return

        # Launch and wait for the command to finish
        job.run()

        # Was this job already considered finished? (Timeout, Crash, etc)
        if job.isFinished():
            return

        # Allow derived proccessResults to process the output and set a failing status (if it failed)
        job_output = job.getOutput()
        output = tester.processResults(tester.getMooseDir(), self.options, job_output)

        # If the tester has not yet failed, append additional information to output
        if not tester.isFail():
            # Read the output either from the temporary file or redirected files
            if tester.hasRedirectedOutput(self.options):
                redirected_output = util.getOutputFromFiles(tester, self.options)
                output += redirected_output

                # If we asked for redirected output but none was found, we'll call that a failure
                if redirected_output == '':
                    tester.setStatus(tester.fail, 'FILE TIMEOUT')
                    output += '\n' + "#"*80 + '\nTester failed, reason: ' + tester.getStatusMessage() + '\n'

        else:
            output += '\n' + "#"*80 + '\nTester failed, reason: ' + tester.getStatusMessage() + '\n'

        # Set testers output with modifications made above so it prints the way we want it
        job.setOutput(output)

        # Test has not yet failed and we are finished... therfor it is a passing test
        if not tester.isFail():
            self.setSuccessfulMessage(tester)

    def setSuccessfulMessage(self, tester):
        """ properly set a finished successful message for tester """
        message = ''

        # Handle 'dry run' first, because if true, job.run() never took place
        if self.options.dry_run:
            message = 'DRY RUN'

        elif tester.specs['check_input']:
            message = 'SYNTAX PASS'

        elif self.options.scaling and tester.specs['scale_refine']:
            message = 'SCALED'

        elif self.options.enable_recover and tester.specs.isValid('skip_checks') and tester.specs['skip_checks']:
            message = 'PART1'

        tester.setStatus(tester.success, message)
