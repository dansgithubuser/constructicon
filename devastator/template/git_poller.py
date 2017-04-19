import buildbot.util.state
import buildbot.changes.base

import os

from twisted.internet import defer
from twisted.python import log

def _decode(x): return x.decode('utf-8')

class ConstructiconGitPoller(buildbot.changes.base.PollingChangeSource, buildbot.util.state.StateMixin):
	compare_attrs=['repo_url', 'work_dir', 'pollInterval', 'project']

	def __init__(self, repo_url, work_dir='git-poller-work', poll_interval=600, project=''):
		buildbot.changes.base.PollingChangeSource.__init__(self, name=repo_url, pollInterval=poll_interval)
		self.repo_url=repo_url
		self.work_dir=work_dir
		self.project=project
		self.branch_to_last_rev={}

	def startService(self):
		self.work_dir=os.path.join(self.master.basedir, self.work_dir)
		d=self.getState('branch_to_last_rev', {})
		def f(x): self.branch_to_last_rev=x
		d.addCallback(f)
		d.addCallback(lambda _: buildbot.changes.base.PollingChangeSource.startService(self))
		d.addErrback(log.err, 'while initializing ConstructiconGitPoller repository')
		return d

	def describe(self):
		return 'ConstructiconGitPoller repo_url: {} work_dir: {}'.format(self.repo_url, self.work_dir)

	def _get_branches(self):
		d=self._vc_cmd('ls-remote')
		d.addCallback(lambda x: [i.split('\t')[1][11:] for i in x.splitlines() if '\trefs/heads/' in i])
		return d

	@defer.inlineCallbacks
	def poll(self):
		if not os.path.exists(os.path.join(self.work_dir, '.git')):
			yield self._vc_cmd('clone', ['--no-checkout', self.repo_url, self.work_dir], '..')
		yield self._vc_cmd('fetch')
		branches=yield self._get_branches()
		for i in branches:
			rev=yield self._vc_cmd('rev-parse', ['origin/'+i])
			yield self._process_changes(rev, i)
			self.branch_to_last_rev[i]=rev
		yield self.setState('branch_to_last_rev', self.branch_to_last_rev)

	def _get_commit_comments(self, rev):
		d=self._vc_cmd('log', ['--no-walk', '--format=%s%n%b', rev, '--'])
		d.addCallback(_decode)
		return d

	def _get_commit_timestamp(self, rev):
		d=self._vc_cmd('log', ['--no-walk', '--format=%ct', rev, '--'])
		d.addCallback(lambda x: float(x))
		return d

	def _get_commit_files(self, rev):
		d=self._vc_cmd('log', ['--name-only', '--no-walk', '--format=%n', rev, '--'])
		def decode_file(file):
			#git use octal char sequences in quotes when non ASCII
			import re
			match=re.match('^"(.*)"$', file)
			if match: file=match.groups()[0].decode('string_escape')
			return _decode(file)
		def process(git_output):
			import itertools
			return [decode_file(file) for file in itertools.ifilter(lambda s: len(s), git_output.splitlines())]
		d.addCallback(process)
		return d

	def _get_commit_author(self, rev):
		d=self._vc_cmd('log', ['--no-walk', '--format=%aN <%aE>', rev, '--'])
		d.addCallback(_decode)
		return d

	@defer.inlineCallbacks
	def _process_changes(self, rev, branch):
		if branch not in self.branch_to_last_rev: return
		if self.branch_to_last_rev[branch]==rev: return
		#log.msg('git poller: processing change: {} from {} branch {}'.format(rev, self.repo_url, branch))
		dl=defer.DeferredList([
			self._get_commit_timestamp(rev),
			self._get_commit_author(rev),
			self._get_commit_files(rev),
			self._get_commit_comments(rev),
		], consumeErrors=True)
		results=yield dl
		#check for failures
		failures=[r[1] for r in results if not r[0]]
		if failures:
			#just fail on the first error; they're probably all related!
			raise failures[0]
		#
		timestamp, author, files, comments=[r[1] for r in results]
		from buildbot.util import epoch2datetime
		yield self.master.addChange(
			author=author,
			revision=rev,
			files=files,
			comments=comments,
			when_timestamp=epoch2datetime(timestamp),
			branch=branch,
			project=self.project,
			repository=self.repo_url,
			src='git',
		)

	def _vc_cmd(self, command, args=[], path='.'):
		path=os.path.normpath(os.path.join(self.work_dir, path))
		from twisted.internet import utils
		d=utils.getProcessOutputAndValue('git', [command]+args, path=path, env=os.environ)
		log.msg('ConstructiconGitPoller git {} in {}'.format(' '.join([command]+args), path))
		def convert_nonzero_to_failure(results, command, args, path):
			'utility to handle the result of getProcessOutputAndValue'
			(stdout, stderr, code)=results
			if code: raise EnvironmentError('command {} {} in {} on repo_url {} failed with exit code {}: {}'.format(
				command, args, path, self.repo_url, code, stderr
			))
			return stdout.strip()
		d.addCallback(convert_nonzero_to_failure, command, args, self.work_dir)
		return d
