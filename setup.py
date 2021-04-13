from distutils.core import setup
import setup_translate


setup(name='enigma2-plugin-extensions-automatic-fullbackup',
		version='4.2',
		author='Dimitrij',
		author_email='dima-73@inbox.lv',
		package_dir={'Extensions.FullBackup': 'src'},
		packages=['Extensions.FullBackup'],
		package_data={'Extensions.FullBackup': ['*.png', '*.sh']},
		description='automatic full backup and manual flashing image',
		cmdclass=setup_translate.cmdclass,
	)

