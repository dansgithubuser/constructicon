#used in go.py example and tests
constructicon={
	'builders': {
		'basic': {
			'features': {'platform': 'linux'},
			'commands': ['python go.py -h'],
			'upload': {'readme.md': 'readme-dest.md'},
		},
		'sleep': {
			'commands': ['python -c "import time; time.sleep(10)"'],
		},
		'deps': {
			'deps': ['https://github.com/dansgithubuser/playground'],
			'commands': ['python ../playground/timestamp.py'],
		},
		'schedulers': {
			'commands': ['python -c "import os; print({lucky_number}); print(os.environ)"'],
			'schedulers': {
				'force-7': {
					'type': 'force',
					'parameters': {'lucky_number': 7},
				},
				'time-42': {
					'type': 'time',
					'hour': '*',
					'minute': '*',
					'parameters': {'lucky_number': 42},
				},
				'commit-13': {
					'type': 'commit',
					'parameters': {'lucky_number': 13},
					'branch_regex': 'test',
				},
			},
		},
		'user-slave': {
			'features': {'platform': 'snes'},
			'commands': ['python go.py -h'],
		},
	},
	'slaves': {
		'user-slave-1': {'platform': 'snes'},
	},
}
