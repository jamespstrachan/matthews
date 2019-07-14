# Vanilla Django Project

Things to do for setup:

- Add .env file in root dir based on env.example
- rename `thefirstapp` dir to a name of your choice
- change `thefirstapp/templates/thefirstapp` dir too
- sed replace in codebase
- check that `project/settings.py` doesn't include things you don't want
- check that default models in `thefirstapp` are applicable, then `manage.py makemigration`
- `manage.py createsuperuser` to make your first user