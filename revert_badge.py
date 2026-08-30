with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    content = f.read()

target = '<span style="font-size:10px;font-weight:500;color:var(--text-secondary);background:var(--bg-hover);border:1px solid var(--border);border-radius:12px;padding:2px 8px;letter-spacing:0.02em;">isteğe bağlı</span>'
replacement = '<span style="font-size:12px;font-weight:500;color:var(--text-secondary);font-style:italic;">(isteğe bağlı)</span>'

if target in content:
    content = content.replace(target, replacement)
    with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
        f.write(content)
    print("Successfully replaced.")
else:
    print("Not found.")
