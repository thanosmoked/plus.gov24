import re

with open('service_bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# **bold** -> <b>bold</b>
content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content, flags=re.DOTALL)

# backtick `code` -> <code>code</code>
content = re.sub(r'`([^`\n]+?)`', r'<code>\1</code>', content)

# parse_mode 통일
content = content.replace("parse_mode='Markdown'", "parse_mode='HTML'")
content = content.replace('parse_mode="Markdown"', 'parse_mode="HTML"')

with open('service_bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
