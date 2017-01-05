#used in go.py example and tests
cybertron={
	'slaves': {
		'slave-1': {'platform': 'linux', 'memory': 'goldfish'},
		'slave-bad': {},
	},
	'megatron_hostname': 'localhost',
	'megatron_master_port': 9120,
	'megatron_slave_port': 9121,
	'devastator_master_port': 9122,
	'devastator_slave_port': 9123,
	'devastator_file_server_port': 9124,
	'builder_base': {
		'features': {'memory': 'goldfish'},
		'deps': ['https://github.com/dansgithubuser/crangen'],
		'precommands': ['echo precommand from cybertron'],
		'commands': ['echo command from cybertron'],
		'upload': {'go.py': 'go.py'},
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
	},
}
