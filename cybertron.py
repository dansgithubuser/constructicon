#used in go.py example and tests
import os

offset=int(os.environ.get('CONSTRUCTICON_PORT_OFFSET', 0))

cybertron={
	'slaves': {
		'slave-1': {'platform': 'linux', 'memory': 'goldfish'},
		'slave-bad': {},
	},
	'megatron_hostname': 'localhost',
	'megatron_master_port': 9120+offset,
	'megatron_slave_port': 9121+offset,
	'devastator_master_port': 9122+offset,
	'devastator_slave_port': 9123+offset,
	'devastator_file_server_port': 9124+offset,
	'horizon': 100,
	'builder_base': {
		'accept': "features['memory']=='goldfish'",
		'deps': ['https://github.com/dansgithubuser/crangen'],
		'precommands': ['echo precommand from cybertron'],
		'commands': ['echo command from cybertron'],
		'upload': {'go.py': 'go.py'},
		'schedulers': ['force-cybertron', 'commit-cybertron'],
	},
	'schedulers': {
		'force-cybertron': {
			'type': 'force',
			'parameters': {'tea': 'secrets'},
		},
		'commit-cybertron': {
			'type': 'commit',
			'branch_regex': 'test-cybertron',
		},
	},
}
