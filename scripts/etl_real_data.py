import os
import uuid
import numpy as np
import pandas as pd
import random

def calculate_labels(row):
    """
    Faz 1 Kural Motoru Mantığı:
    1. FTR Sevki: Tırnak tutulumu VEYA (Sabah tutukluğu > 30dk)
    2. Sistemik Tedavi Sevki: PASI > 10 VEYA BSA > 10 VEYA DLQI > 10 VEYA (PASI > 5 VE DLQI > 5)
    3. Aile Hekimi Sevki: VKİ > 30 VEYA LDL > 130
    """
    ftr = bool(row.get('tirnak_tutulumu', False) or row.get('sabah_turuklugu_30dk', False))
    
    pasi = row.get('pasi_skoru', 0)
    dlqi = row.get('dlqi', 0)
    bsa = row.get('bsa', 0)
    sistemik = bool(pasi > 10 or bsa > 10 or dlqi > 10 or (pasi > 5 and dlqi > 5))
    
    vki = row.get('vki', 0)
    ldl = row.get('ldl', 0)
    aile = bool(vki > 30 or ldl > 130)
    
    return pd.Series({'ftr': ftr, 'aile_hekimligi': aile, 'sistemik_tedavi': sistemik})

def load_dcpr(path):
    print(f"Loading DCPR from {path}")
    df = pd.read_excel(path)
    df_clean = pd.DataFrame()
    
    # Sex: 1=Male (E), 2=Female (K)
    df_clean['cinsiyet'] = df['Sex'].map({1: 'E', 2: 'K'})
    df_clean['yas'] = df['Age']
    df_clean['vki'] = df['BMI']
    df_clean['pasi_skoru'] = df['PASI  ']
    df_clean['dlqi'] = df['DLQI']
    df_clean['sigara'] = df['Smoking'].astype(bool)
    df_clean['hastalik_suresi_ay'] = df['Duration_yrs'] * 12
    df_clean['bsa'] = np.nan # DCPR'da yok
    df_clean['psa_durumu'] = np.nan # PsA bilgisi yok
    df_clean['kohort_adi'] = 'DCPR'
    
    return df_clean

def load_il17(path, cohort_name, col_offset=0):
    print(f"Loading IL-17 from {path}")
    df = pd.read_excel(path)
    # Row 0 contains subheaders, data starts at row 1
    df_data = df.iloc[1:].copy()
    
    df_clean = pd.DataFrame()
    
    # Płeć 0-M 1-K -> 0=Male, 1=Female
    df_clean['cinsiyet'] = df_data['Płeć 0-M 1-K'].map({0: 'E', 1: 'K'})
    df_clean['yas'] = pd.to_numeric(df_data['Wiek'], errors='coerce')
    df_clean['vki'] = pd.to_numeric(df_data['BMI'], errors='coerce')
    df_clean['hastalik_suresi_ay'] = pd.to_numeric(df_data['Wywiad chorobowy (lata)'], errors='coerce') * 12
    df_clean['psa_durumu'] = pd.to_numeric(df_data['ŁZS 0-nie 1-tak'], errors='coerce').fillna(0).astype(bool)
    
    # Baseline columns
    df_clean['pasi_skoru'] = pd.to_numeric(df_data.iloc[:, 12 + col_offset].replace(['x', 'PASI', 'PASI-1', 'brak danych'], np.nan), errors='coerce')
    df_clean['bsa'] = pd.to_numeric(df_data.iloc[:, 13 + col_offset].replace(['x', 'BSA', 'BSA-1', 'brak danych'], np.nan), errors='coerce')
    df_clean['dlqi'] = pd.to_numeric(df_data.iloc[:, 14 + col_offset].replace(['x', 'DLQI', 'DLQI-1', 'brak danych'], np.nan), errors='coerce')
    
    df_clean['sigara'] = np.nan
    df_clean['kohort_adi'] = cohort_name
    
    return df_clean

def run_etl():
    datasets_dir = "datasets"
    dcpr_path = os.path.join(datasets_dir, "Database DCPR psoriasis", "A-Database.xls")
    bim_path = os.path.join(datasets_dir, "Interleukin-17 inhibitors in the treatment of mode", "Bimekizumab - supplementary material.xlsx")
    ixe_path = os.path.join(datasets_dir, "Interleukin-17 inhibitors in the treatment of mode", "Ixekizumab - supplementary material.xlsx")
    sec_path = os.path.join(datasets_dir, "Interleukin-17 inhibitors in the treatment of mode", "Secukinumab - supplementary material.xlsx")
    
    df_dcpr = load_dcpr(dcpr_path)
    df_bim = load_il17(bim_path, "IL17_BIM", col_offset=0)
    df_ixe = load_il17(ixe_path, "IL17_IXE", col_offset=0)
    df_sec = load_il17(sec_path, "IL17_SEC", col_offset=1) # Secukinumab has extra column before PASI
    
    # Birleştir
    df_master = pd.concat([df_dcpr, df_bim, df_ixe, df_sec], ignore_index=True)
    
    # Hasta ID ata
    df_master['hasta_id'] = [str(uuid.uuid4()) for _ in range(len(df_master))]
    
    # ---------------------------------------------------------
    # HİBRİT İMPUTASYON (Sentetik Veri Üretimi)
    # ---------------------------------------------------------
    np.random.seed(42)
    random.seed(42)
    
    # PASI eksikse DLQI'ye bakarak doldur (basit lineer regresyon benzeri: PASI ~ DLQI * 1.5) veya ortalama ile
    mean_pasi = df_master['pasi_skoru'].mean()
    df_master['pasi_skoru'] = df_master.apply(
        lambda row: max(1.0, min(72.0, row['dlqi'] * 1.5 + random.uniform(-2, 2))) if pd.isna(row['pasi_skoru']) and not pd.isna(row['dlqi']) else (row['pasi_skoru'] if not pd.isna(row['pasi_skoru']) else mean_pasi),
        axis=1
    )
    
    # BSA eksikse PASI'den tahmin et
    df_master['bsa'] = df_master.apply(
        lambda row: max(1.0, min(100.0, row['pasi_skoru'] * 1.2 + random.uniform(-5, 5))) if pd.isna(row['bsa']) else row['bsa'],
        axis=1
    )
    
    # Sigara: %35 olasılıkla ata (DCPR'da var, diğerlerinde yok)
    df_master['sigara'] = df_master['sigara'].apply(lambda x: x if pd.notna(x) else random.random() < 0.35)
    
    # LDL: VKI ve Yaşa göre sentetik
    # Base: 110. VKI > 30 ise +20. Yas > 50 ise +10. Random noise.
    def impute_ldl(row):
        base = 110.0
        if row['vki'] > 30: base += 25
        elif row['vki'] > 25: base += 10
        if row['yas'] > 50: base += 15
        return max(50.0, min(300.0, base + np.random.normal(0, 15)))
        
    df_master['ldl'] = df_master.apply(impute_ldl, axis=1)
    
    # Tırnak tutulumu (binary): PASI yüksekse daha olası.
    def impute_nail(row):
        prob = 0.4
        if row['pasi_skoru'] > 15: prob = 0.6
        return random.random() < prob
        
    df_master['tirnak_tutulumu'] = df_master.apply(impute_nail, axis=1)
    
    # Sabah tutukluğu > 30dk (binary): IL-17 kohortlarında PsA olanlarda %80, diğerlerinde %25.
    def impute_morning_stiff(row):
        if pd.notna(row['psa_durumu']) and row['psa_durumu']:
            return random.random() < 0.80
        return random.random() < 0.25
        
    df_master['sabah_turuklugu_30dk'] = df_master.apply(impute_morning_stiff, axis=1)
    
    # Temizle
    df_master = df_master.dropna(subset=['vki', 'yas'])
    
    # ---------------------------------------------------------
    # HEDEF ETİKET (LABEL) ÜRETİMİ
    # ---------------------------------------------------------
    labels = df_master.apply(calculate_labels, axis=1)
    df_master = pd.concat([df_master, labels], axis=1)
    
    # Schema_version
    df_master['schema_version'] = "2.0"
    df_master['is_synthetic'] = True # Hibrit olduğu için
    
    # İhtiyacımız olmayan sütunları sil (psa_durumu sadece hesaplama için lazımdı)
    df_master = df_master.drop(columns=['psa_durumu'])
    
    # Çıktı Dizini
    out_dir = "data/real"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "hybrid_master_dataset.parquet")
    
    df_master.to_parquet(out_path, index=False)
    print(f"\nETL tamamlandı. {len(df_master)} satır veri {out_path} adresine kaydedildi.")
    
    print("\nOluşturulan Etiket Dağılımı:")
    print("FTR Sevki:", df_master['ftr'].sum(), f"({df_master['ftr'].mean():.1%})")
    print("Aile Hekimliği:", df_master['aile_hekimligi'].sum(), f"({df_master['aile_hekimligi'].mean():.1%})")
    print("Sistemik Tedavi:", df_master['sistemik_tedavi'].sum(), f"({df_master['sistemik_tedavi'].mean():.1%})")

if __name__ == "__main__":
    run_etl()
