import ast
files = ['service_bot.py', 'database_schema.py', 'web.py']
for f in files:
    try:
        ast.parse(open(f, encoding='utf-8').read())
        print(f'OK: {f}')
    except SyntaxError as e:
        print(f'ERROR: {f} - {e}')
