#used in go.py example and tests
constructicon={
	'builders': {
		'basic': {
			'accept': "features['platform']=='linux'",
			'commands': ['python go.py -h'],
			'schedulers': ['force-7'],
			'upload': {
				'readme.md': 'readme-dest.md',
				'constructicon.py': 'constructicon-dest.py',
				'devastator': 'devastator-dest',
			},
			'zip': ['constructicon-dest.py', 'devastator'],
			'unzip': ['devastator-dest'],
			'url': {'devastator-dest': 'devastator/template'},
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
			'schedulers': ['force-7', 'time-42', 'commit-13'],
		},
		'user-slave': {
			'accept': "features['platform']=='snes' and features['memory']=='goldfish'",
			'commands': ['python go.py -h'],
		},
		'get': {
			'get': {'constructicon-basic': ["build['number']"]},
			'commands': [
				constructicon_slave_go('g get'),
				'python ../constructicon-basic/constructicon-dest.py',
			],
		},
	},
	'schedulers': {
		'force-7': {
			'type': 'force',
			'parameters': {'lucky_number': 7, 'version': ''},
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
	'slaves': {
		'constructicon-user-slave-1': {'platform': 'snes', 'memory': 'goldfish'},
		'constructicon-user-slave-bad': {},
	},
}
