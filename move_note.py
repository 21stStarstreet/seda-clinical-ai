with open("cdss_web/Components/Pages/Predict.razor", "r") as f:
    content = f.read()

hekim_notu_block = """
                        <div class="form-group">
                            <label class="form-label">Hekim Notu</label>
                            <textarea class="form-input"
                                      placeholder="Klinik gözlemler, ek notlar…"
                                      rows="2"
                                      @bind="_hekimNotu"
                                      style="resize:vertical;"></textarea>
                        </div>"""

# Remove from current location
content = content.replace(hekim_notu_block, "")

# Insert before Submit section
submit_marker = "            <!-- Submit -->"
new_hekim_notu_block = """            <!-- Hekim Notu -->
            <div class="form-group" style="margin-bottom:24px;">
                <label class="form-label">
                    Hekim Notu
                    <span style="font-size:12px;font-weight:500;color:var(--text-secondary);font-style:italic;">(isteğe bağlı)</span>
                </label>
                <textarea class="form-input"
                          placeholder="Klinik gözlemler, ek notlar (Bu not PDF raporuna eklenecektir)…"
                          rows="3"
                          @bind="_hekimNotu"
                          style="resize:vertical;"></textarea>
            </div>

            <!-- Submit -->"""

content = content.replace(submit_marker, new_hekim_notu_block)

with open("cdss_web/Components/Pages/Predict.razor", "w") as f:
    f.write(content)

print("Hekim Notu moved successfully.")
