with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    content = f.read()

target = '<span style="font-size:11px;font-weight:400;color:var(--text-muted);">(isteğe bağlı)</span>'
replacement = '<span style="font-size:10px;font-weight:500;color:var(--text-secondary);background:var(--bg-hover);border:1px solid var(--border);border-radius:12px;padding:2px 8px;letter-spacing:0.02em;">isteğe bağlı</span>'

if target in content:
    content = content.replace(target, replacement)
    with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
        f.write(content)
    print("Successfully replaced.")
else:
    print("Target string not found. Trying regex...")
    import re
    content = re.sub(r'<span[^>]*>\(isteğe bağlı\)</span>', replacement, content)
    with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
        f.write(content)
    print("Replaced using regex.")

