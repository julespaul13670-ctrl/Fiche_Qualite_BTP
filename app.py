import gspread
from google.oauth2.service_account import Credentials
import base64
import streamlit as st
from fpdf import FPDF
from datetime import datetime
import pandas as pd
import os
import smtplib
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import datetime
import imaplib
import email
from email.header import decode_header

def connecter_drive():
    scope = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
    
    # SI TU ES SUR TON PC :
    path_to_json = "cle_google.json" # Mets le nom exact de ton fichier
    if os.path.exists(path_to_json):
        creds = Credentials.from_service_account_file(path_to_json, scopes=scope)
    else:
        # SI TU ES SUR STREAMLIT CLOUD (plus tard) :
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        
    return gspread.authorize(creds)

def charger_toutes_les_donnees_sheet():
    try:
        client = connecter_drive()
        # On ouvre le fichier par son nom exact
        sh = client.open("Configuration_Questions").sheet1
        
        # On récupère les données
        data = sh.get_all_records()
        
        if not data:
            st.warning("Le fichier Google Sheets est vide.")
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        # On s'assure qu'on ne prend pas les lignes totalement vides
        df = df[df['Ouvrage'] != ""]
        return df
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier 'Configuration_Questions' : {e}")
        return None

# --- INITIALISATION AU DÉMARRAGE ---
# Place ceci juste après tes imports et la config de la page
# --- INITIALISATION AU DÉMARRAGE ---
if "df_config" not in st.session_state:
    with st.spinner("Connexion au Cloud en cours..."):
        data_cloud = charger_toutes_les_donnees_sheet()
        if data_cloud is not None:
            st.session_state.df_config = data_cloud
        else:
            st.session_state.df_config = pd.DataFrame(columns=["Ouvrage", "Niveau", "Sous-Catégorie / Type", "Catégorie Question", "Question ou Option"])

def lire_mdp():
    file_pwd = "admin_pwd.txt"
    if os.path.exists(file_pwd):
        with open(file_pwd, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "1234" # Mot de passe par défaut si le fichier n'existe pas encore

def valider_numero_csv(chantier_nom, pref, num):
    try:
        file_csv = "suivi_codes.csv"
        # 1. Charger le fichier ou en créer un nouveau s'il n'existe pas
        if os.path.exists(file_csv):
            df = pd.read_csv(file_csv)
        else:
            df = pd.DataFrame(columns=["Chantier", "Pref", "Num"])

        # 2. Vérifier si une ligne existe déjà pour ce chantier et ce préfixe
        filtre = (df['Chantier'] == chantier_nom) & (df['Pref'] == pref)
        
        if filtre.any():
            # On met à jour le numéro existant
            df.loc[filtre, 'Num'] = num
        else:
            # On ajoute une nouvelle ligne
            nouvelle_ligne = pd.DataFrame([{"Chantier": chantier_nom, "Pref": pref, "Num": num}])
            df = pd.concat([df, nouvelle_ligne], ignore_index=True)

        # 3. Sauvegarder sur le disque
        df.to_csv(file_csv, index=False)
        return True
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du compteur : {e}")
        return False
    
def envoyer_par_email(pdf_bytes, nom_fichier, chantier, ouvrage):
    try:
        # 1. CONFIGURATION (Utilise tes identifiants Gmail)
        expediteur = "fichequalitetp@gmail.com"
        # Ton code d'application Google (les 16 lettres)
        mot_de_passe = "feculdalnfoyotdb" 
        destinataire = "fichequalitetp@gmail.com" # Tu t'envoies le mail à toi-même

        # 2. CRÉATION DU MAIL
        msg = MIMEMultipart()
        msg['From'] = expediteur
        msg['To'] = destinataire
        
        # Objet précis pour que les Archives puissent le lire plus tard
        date_str = datetime.datetime.now().strftime("%d/%m/%Y")
        # Format : RAPPORT ID - CHANTIER - OUVRAGE - DATE
        msg['Subject'] = f"RAPPORT {nom_fichier.split('_')[1]} - {chantier} - {ouvrage} - {date_str}"

        corps = f"Veuillez trouver ci-joint le rapport qualité pour le chantier {chantier}.\nOuvrage : {ouvrage}\nDate : {date_str}"
        msg.attach(MIMEText(corps, 'plain'))

        # 3. PIÈCE JOINTE (Le PDF)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {nom_fichier}")
        msg.attach(part)

        # 4. ENVOI VIA LE SERVEUR GMAIL
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(expediteur, mot_de_passe)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erreur d'envoi mail : {e}")
        return False
    
class FicheQualite(FPDF):
    def header(self):
        # 1. LOGO GAUCHE (ex: Logo Entreprise)
        if os.path.exists("image/logo_gauche.png"):
            self.image("image/logo_gauche.png", 10, 8, 27) # x=10, y=8, largeur=33
            
        # 2. LOGO DROITE (ex: Logo Client ou Certification)
        if os.path.exists("image/logo_droit.png"):
            # On le place à 10mm du bord droit (210mm largeur A4 - 10mm marge - 33mm image = 167)
            self.image("image/logo_droit.png", 160, 12, 37) 
            
        # 3. TITRE CENTRAL
        self.set_font('Arial', 'B', 15)
        # On décale pour ne pas écrire sur le logo de gauche
        self.cell(80) 
        self.cell(30, 10, 'FICHE DE CONTROLE QUALITE', 0, 0, 'C')
        
        # Saut de ligne pour le contenu
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

# --- 1. CONFIGURATION ---
    st.set_page_config(page_title="Qualité Exécution VRD", layout="wide")
# --- 2. CSS "FORCE BRUTE" POUR CARTES GÉANTES ---
st.markdown("""
    <style>
    /* On cible les boutons de la page d'accueil via leur clé */
    div.stButton > button[key^="home_"] {
        width: 100% !important; 
        min-height: 550px !important; /* HAUTEUR GÉANTE */
        background-color: white !important;
        border: 4px solid #e0e0e0 !important;
        border-radius: 35px !important;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1) !important;
        transition: all 0.4s ease-in-out !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
    }

    /* Style du texte (émoji + titre) */
    div.stButton > button[key^="home_"] p {
        font-size: 40px !important; /* TAILLE DU TEXTE */
        font-weight: bold !important;
        color: #2c3e50 !important;
        line-height: 1.6 !important;
        white-space: pre-line !important;
    }

    /* Effet au survol */
    div.stButton > button[key^="home_"]:hover {
        border-color: #3498db !important;
        transform: translateY(-15px) !important;
        box-shadow: 0 30px 60px rgba(52, 152, 219, 0.2) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialisation de l'état de la page
if "page" not in st.session_state:
    st.session_state.page = "Accueil"

# --- 3. BARRE LATÉRALE ---
with st.sidebar:
    st.title("🚧 Menu Principal")
    options = {"🏠 Accueil": "Accueil", "📝 Ajouter": "Ajouter", "📂 Archives": "Archives", "⚙️ Paramètres": "Paramètres"}
    
    current_page = st.session_state.page
    idx = list(options.values()).index(current_page) if current_page in options.values() else 0
    
    choix = st.radio("Navigation", list(options.keys()), index=idx)
    if options[choix] != st.session_state.page:
        st.session_state.page = options[choix]
        st.rerun()

# --- 4. LOGIQUE DES PAGES ---

if st.session_state.page == "Accueil":
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center;'>🏗️ Gestionnaire Qualité BTP</h1>", unsafe_allow_html=True)
    st.write("---")

    # On utilise 2 colonnes larges au centre
    _, col1, col2, _ = st.columns([0.5, 2, 2, 0.5])

    with col1:
        # L'utilisation de \n crée les retours à la ligne dans la carte
        if st.button("➕\n\nAJOUTER UN\nDOCUMENT", key="home_add"):
            st.session_state.page = "Ajouter"
            st.rerun()

    with col2:
        if st.button("📁\n\nCONSULTER LES\nARCHIVES", key="home_arch"):
            st.session_state.page = "Archives"
            st.rerun()


elif st.session_state.page == "Ajouter":
    st.title("📝 Nouveau Rapport de Contrôle")

    file_ch = "data_chantiers.csv"
    file_ctrl = "data_controleurs.csv"
    

    if os.path.exists(file_ch) and os.path.exists(file_ctrl):
        df_ch = pd.read_csv(file_ch)
        dict_chantiers = pd.Series(df_ch.Responsable.values, index=df_ch.Nom).to_dict()
        liste_personnel = pd.read_csv(file_ctrl)["Nom"].tolist()
        

        chantier = st.selectbox("📍 Choisir le chantier", ["Sélectionner..."] + list(dict_chantiers.keys()))
        if chantier != "Sélectionner...":
            st.info(f"Responsable : **{dict_chantiers.get(chantier, '')}**")
            c1, c2 = st.columns(2)
            with c1:
                choix_nom = st.selectbox("👤 Contrôleur", ["Sélectionner..."] + liste_personnel + ["Autre..."])
                nom_final = st.text_input("1er lettre Prenom + NOM") if choix_nom == "Autre..." else (choix_nom if choix_nom != "Sélectionner..." else "")
            with c2:
                date_auto = st.date_input("📅 Date", datetime.datetime.now())

            st.divider()
            # --- 1. SÉLECTION CASCADE ---
        df = st.session_state.df_config
        
        # On définit une liste vide par défaut pour éviter l'erreur NameError
        liste_ouvrages = [] 
        
        if df is not None and not df.empty:
            liste_ouvrages = [ov for ov in df['Ouvrage'].unique() if ov != "_GENERAL" and ov != ""]
        
        # Maintenant 'liste_ouvrages' existe toujours, même si elle est vide []
        
        # 1. Sélection de l'Ouvrage (Regards, Bordures...)
        # Modifie la création de la liste
            # --- 1. SÉLECTION DE L'OUVRAGE ---
        # --- 1. SÉLECTION DE L'OUVRAGE ---
        liste_ouvrages = [ov for ov in df['Ouvrage'].unique() if ov != "_GENERAL" and ov != ""]
        liste_ouvrages.append("Autre")

        ouvrage_sel = st.selectbox("🏗️ Ouvrage à contrôler", ["Sélectionner..."] + liste_ouvrages, key="sel_ouv_main")

        if ouvrage_sel != "Sélectionner...":
            # --- 2. GESTION DU CAS 'AUTRE' VS NORMAL ---
            if ouvrage_sel == "Autre":
                nom_ouvrage_libre = st.text_input("📝 Nom de l'ouvrage non prévu", placeholder="Ex: Muret, Escalier...")
                ouvrage_final_nom = nom_ouvrage_libre if nom_ouvrage_libre else "Autre ouvrage"
                # On crée un DataFrame vide avec les colonnes du Sheets pour éviter les erreurs NameError
                df_ouv = pd.DataFrame(columns=df.columns)
                st.info("💡 Pour cet ouvrage, vous pouvez remplir les contrôles généraux et l'observation ci-dessous.")
            else:
                df_ouv = df[df['Ouvrage'] == ouvrage_sel]
                ouvrage_final_nom = ouvrage_sel

            # --- 3. SOUS-CATÉGORIES ---
            df_scat = df_ouv[df_ouv['Niveau'].isin(['S-Cat', 'Type'])]
            sc_sel = "Standard" # Valeur par défaut si vide
            
            if not df_scat.empty:
                sc_list = df_scat['Sous-Catégorie / Type'].unique().tolist()
                sc_sel = st.selectbox("🔍 Sous-catégorie / Modèle", ["Sélectionner..."] + sc_list, key="sel_scat")

                if sc_sel != "Sélectionner...":
                    df_filtre_sc = df_scat[df_scat['Sous-Catégorie / Type'] == sc_sel]
                    deja_affiche = []

                    for i, row in df_filtre_sc.iterrows():
                        question_texte = row['Question ou Option']
                        if pd.isna(question_texte) or str(question_texte).strip() == "":
                            continue

                        if row['Niveau'] == 'Type':
                            if sc_sel not in deja_affiche:
                                st.radio(f"Configuration {sc_sel}", ["Ligne droite", "Courbe"], key=f"rad_{sc_sel}_{i}")
                                deja_affiche.append(sc_sel)
                        else:
                            st.checkbox(str(question_texte), key=f"chk_{question_texte}")

            # --- 4. QUESTIONS FIXES DE L'OUVRAGE ---
            df_fixes = df_ouv[df_ouv['Niveau'] == 'Ouvrage']
            if not df_fixes.empty:
                st.subheader(f"✅ Points de contrôle {ouvrage_final_nom}")
                for i, row in df_fixes.iterrows():
                    st.checkbox(row['Question ou Option'], key=f"chk_{row['Question ou Option']}")

            # --- 5. QUESTIONS GÉNÉRALES ---
            st.subheader("🌍 Contrôles Généraux")
            df_gen_data = df[df['Ouvrage'] == '_GENERAL']
            for i, row in df_gen_data.iterrows():
                q_txt = str(row['Question ou Option']).strip()
                st.checkbox(q_txt, key=f"chk_gen_{q_txt}")

            # --- 6. OBSERVATIONS ET PHOTO ---
            st.divider()
            commentaire = st.text_area("📝 Observations particulières", key="comm_zone")
            # --- 6. Capture ou Import Photo ---
            st.subheader("📸 Justificatif Photo")
            
            # file_uploader permet de choisir entre l'appareil photo et la galerie sur mobile
            photo = st.file_uploader(
                "Prendre une photo ou choisir une image", 
                type=['png', 'jpg', 'jpeg'],
                key=f"upload_{ouvrage_sel}"
            )
            if photo:
                st.image(photo, caption="Aperçu de la photo sélectionnée", width=300)
                # Stockage en session
                st.session_state['temp_photo_bytes'] = photo.getvalue()

            # --- 7. BOUTON DE GÉNÉRATION (CONTENU INCHANGÉ) ---
            if st.button("🚀 1. Générer l'Aperçu", key=f"btn_generer_{ouvrage_sel}"):
                if not nom_final:
                    st.error("Indiquez le contrôleur.")
                else:
                    try:
                        # 1. RÉCUPÉRATION DES RÉPONSES
                        controles = {}
                        # Questions Ouvrage
                        for _, row in df_ouv.iterrows():
                            q_txt = row['Question ou Option']
                            key_chk = f"chk_{q_txt}"
                            if key_chk in st.session_state:
                                controles[q_txt] = (st.session_state[key_chk], row['Catégorie Question'])

                        # Questions Générales
                        for _, row in df_gen_data.iterrows():
                            q_txt = str(row['Question ou Option']).strip()
                            key_gen = f"chk_gen_{q_txt}"
                            if key_gen in st.session_state:
                                cat_name = row['Catégorie Question'] if pd.notna(row['Catégorie Question']) else "Général"
                                controles[q_txt] = (st.session_state[key_gen], cat_name)

                        # 2. LOGIQUE ID INTELLIGENT
                        if ouvrage_sel == "Autre":
                            pref_final = "AU"
                        else:
                            char_ov = ouvrage_sel[0].upper()
                            char_sc = sc_sel[0].upper() if sc_sel != "Standard" else "G"
                            pref_final = f"{char_ov}{char_sc}"

                        df_suivi = pd.read_csv("suivi_codes.csv") if os.path.exists("suivi_codes.csv") else pd.DataFrame(columns=["Chantier", "Pref", "Num"])
                        filtre = (df_suivi['Chantier'] == chantier) & (df_suivi['Pref'] == pref_final)
                        nouveau_num = int(df_suivi.loc[filtre, 'Num'].iloc[0]) + 1 if filtre.any() else 1
                        code_fiche = f"{pref_final}-{nouveau_num:03d}"

                        # 3. GÉNÉRATION PDF (TA MISE EN PAGE EXACTE)
                        pdf = FicheQualite()
                        pdf.add_page()
                        
                        # Titre ouvrage libre ou sélectionné
                        
                        pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 12)
                        pdf.cell(0, 10, f"Rapport : {chantier}", 1, 1, 'L', fill=True); pdf.ln(5)
                        
                        pdf.set_font("Arial", 'B', 10); pdf.cell(25, 8, "Responsable : ", 0, 0)
                        pdf.set_font("Arial", '', 10); pdf.cell(85, 8, f"{dict_chantiers[chantier]}", 0, 0)
                        pdf.set_font("Arial", 'B', 10); pdf.cell(40, 8, "ID : ", 0, 0, 'R')
                        pdf.set_font("Arial", '', 10); pdf.cell(20, 8, f"{code_fiche}", 0, 1, 'L')

                        pdf.set_font("Arial", 'B', 10); pdf.cell(25, 8, "Controleur: ", 0, 0)
                        pdf.set_font("Arial", '', 10); pdf.cell(85, 8, f"{nom_final}", 0, 0)
                        pdf.set_font("Arial", 'B', 10); pdf.cell(40, 8, "Ouvrage : ", 0, 0, 'R')
                        sc_display = sc_sel if 'sc_sel' in locals() else "Général"
                        pdf.set_font("Arial", '', 10); pdf.cell(20, 8, f"{ouvrage_sel} ({sc_display})", 0, 1, 'L')
                        pdf.ln(8)

                        # Tableau des points de contrôle
                        pdf.set_fill_color(230, 230, 230); pdf.set_font("Arial", 'B', 10)
                        pdf.cell(40, 10, "Catégorie", 1, 0, 'C', fill=True)
                        pdf.cell(100, 10, "Point de contrôle", 1, 0, 'C', fill=True)
                        pdf.cell(50, 10, "Statut", 1, 1, 'C', fill=True)

                        pdf.set_font("Arial", '', 9)
                        for pt_txt, info in controles.items():
                            etat, cat_name = info
                            pdf.cell(40, 10, str(cat_name), 1, 0, 'L')
                            pdf.cell(100, 10, str(pt_txt), 1, 0, 'L')
                            status = "OK" if etat else "NON CONFORME"
                            if not etat: pdf.set_text_color(200, 0, 0)
                            pdf.cell(50, 10, status, 1, 1, 'C')
                            pdf.set_text_color(0, 0, 0)

                        # Observations
                        pdf.ln(10)
                        if commentaire.strip():
                            pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "OBSERVATIONS :", 0, 1, 'L')
                            pdf.set_font("Arial", '', 11); pdf.multi_cell(0, 8, commentaire, border=1, align='L')
                            pdf.ln(5)

                        # Photo
                        if photo:
                            pdf.add_page()
                            pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "Photo de l'ouvrage :", 0, 1, 'L')
                            with open("temp_photo.png", "wb") as f:
                                f.write(photo.getbuffer())
                            pdf.image("temp_photo.png", x=10, y=30, w=180)

                        # Finalisation et stockage session
                        pdf_data = pdf.output(dest='S')
                        st.session_state.pdf_bytes = bytes(pdf_data) if not isinstance(pdf_data, str) else pdf_data.encode('latin-1')
                        st.session_state.nom_fichier = f"Rapport_{code_fiche}_{chantier}.pdf"
                        st.session_state.temp_num = nouveau_num
                        st.session_state.temp_pref = pref_final
                        st.success(f"✅ Aperçu prêt ! ({code_fiche})")

                    except Exception as e:
                        st.error(f"Erreur technique : {e}")

            # --- 8. AFFICHAGE DE L'APERÇU ET ENVOI ---
            if st.session_state.get('pdf_bytes'):
                b64 = base64.b64encode(st.session_state.pdf_bytes).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>', unsafe_allow_html=True)
                
                if st.button("💾 2. Sauvegarder & Envoyer"):
                    if envoyer_par_email(st.session_state.pdf_bytes, st.session_state.nom_fichier, chantier, ouvrage_sel):
                        valider_numero_csv(chantier, st.session_state.temp_pref, st.session_state.temp_num)
                        st.toast('Rapport envoyé !', icon='🚀')
                        st.success("Envoyé !")
                        st.session_state.pdf_bytes = None
                        if 'temp_photo' in st.session_state:
                            del st.session_state['temp_photo']
                
                # 4. RELANCE DE LA PAGE
                # Cela remet l'interface à zéro pour le prochain ouvrage
                        st.rerun()
elif st.session_state.page == "Archives":
    st.header("📂 Archives des Rapports (Cloud)")
    
    # 1. BARRE D'OUTILS
    col_search, col_date = st.columns([2, 1])
    with col_search:
        search_query = st.text_input("🔍 Rechercher un fichier", placeholder="ID, chantier, ouvrage...")
    with col_date:
        date_sel = st.date_input("📅 Filtrer par date", value=None)

    st.write("---")

    # 2. BOUTON DE SYNCHRONISATION
    if st.button("🔄 Synchroniser les archives"):
        with st.spinner("Recherche des rapports..."):
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login("fichequalitetp@gmail.com", "feculdalnfoyotdb")
                mail.select("INBOX")
                status, messages = mail.search(None, '(SUBJECT "RAPPORT")')
                mail_ids = messages[0].split()
                data_list = []
                for i in range(len(mail_ids)-1, max(-1, len(mail_ids)-41), -1):
                    res, msg_data = mail.fetch(mail_ids[i], "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes): 
                                subject = subject.decode(encoding if encoding else "utf-8")
                            parts = subject.split(" - ")
                            if len(parts) >= 4:
                                data_list.append({
                                    "ID": parts[0].replace("RAPPORT ", ""),
                                    "Chantier": parts[1],
                                    "Ouvrage": parts[2],
                                    "Date": parts[3],
                                    "Mail_ID": mail_ids[i]
                                })
                mail.logout()
                st.session_state.archives_data = data_list
            except Exception as e:
                st.error(f"Erreur : {e}")

    # 3. AFFICHAGE DU TABLEAU
    if "archives_data" in st.session_state:
        df = pd.DataFrame(st.session_state.archives_data)
        
        # Filtres
        if search_query:
            df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        if date_sel:
            d_str = date_sel.strftime('%d/%m/%Y')
            df = df[df['Date'] == d_str]

        # --- NOUVEAU : ZONE D'AFFICHAGE DU PDF (S'affiche en haut si un PDF est sélectionné) ---
        if "current_pdf" in st.session_state and st.session_state.current_pdf:
            st.write("---")
            c_titre, c_fermer = st.columns([5, 1])
            c_titre.subheader("📄 Consultation du rapport")
            if c_fermer.button("❌ Fermer l'aperçu"):
                st.session_state.current_pdf = None
                st.rerun()
            
            st.markdown(st.session_state.current_pdf, unsafe_allow_html=True)
            st.write("---")

        st.metric(label="Rapports trouvés", value=len(df))
        st.write("---")

        # --- EN-TÊTE FIXE DU TABLEAU ---
        h1, h2, h3, h4, h5 = st.columns([1, 2, 2, 2, 1])
        h1.write("**ID**")
        h2.write("**Chantier**")
        h3.write("**Ouvrage**")
        h4.write("**Date**")
        h5.write("**Action**")
        st.divider()

        if not df.empty:
            for index, row in df.iterrows():
                c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 1])
                c1.write(row['ID'])
                c2.write(row['Chantier'])
                c3.write(row['Ouvrage'])
                c4.write(row['Date'])
                
                if c5.button("Consulter", key=f"arch_{row['Mail_ID'].decode()}"):
                    with st.spinner("Récupération du PDF..."):
                        try:
                            m = imaplib.IMAP4_SSL("imap.gmail.com")
                            m.login("fichequalitetp@gmail.com", "feculdalnfoyotdb")
                            m.select("INBOX")
                            _, data = m.fetch(row['Mail_ID'], "(RFC822)")
                            msg = email.message_from_bytes(data[0][1])
                            for part in msg.walk():
                                if part.get_content_maintype() == 'multipart': continue
                                if part.get('Content-Disposition') is None: continue
                                filename = part.get_filename()
                                if filename and filename.lower().endswith(".pdf"):
                                    pdf_content = part.get_payload(decode=True)
                                    base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
                                    # ON STOCKA DANS LE SESSION STATE AU LIEU D'AFFICHER DIRECTEMENT
                                    st.session_state.current_pdf = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                            m.logout()
                            st.rerun() # On relance pour afficher le PDF en haut
                        except Exception as e:
                            st.error(f"Erreur : {e}")
        else:
            st.warning("Aucun rapport ne correspond à votre recherche.")
    else:
        st.info("Utilisez le bouton ci-dessus pour charger vos rapports depuis Gmail.")


elif st.session_state.page == "Paramètres":
    st.header("⚙️ Configuration Système")
    
    # --- 1. SYSTÈME DE VERROUILLAGE (Vérification du MDP) ---
    if not st.session_state.get("auth_admin", False):
        st.subheader("🔐 Accès Restreint")
        mdp_saisi = st.text_input("Entrez le mot de passe administrateur", type="password", key="login_admin")
        
        if mdp_saisi:
            if mdp_saisi == lire_mdp():
                st.session_state.auth_admin = True
                st.success("✅ Accès accordé")
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect")
        
        # Très important : on arrête l'exécution ici si l'utilisateur n'est pas authentifié
        st.stop()
    else:
        if st.button("🔓 Déconnexion"): st.session_state.auth_admin = False; st.rerun()
        st.write("---")
        tab1, tab2, tab3, tab4 = st.tabs(["🏗️ Chantiers", "👤 Contrôleurs", "📐 Structure & Questions", "🔑 Sécurité"])

        with tab1:
            df_ch = pd.read_csv("data_chantiers.csv") if os.path.exists("data_chantiers.csv") else pd.DataFrame(columns=["Nom", "Responsable"])
            e_ch = st.data_editor(df_ch, num_rows="dynamic", key="ed_ch", use_container_width=True)
            if st.button("Sauvegarder Chantiers"): e_ch.to_csv("data_chantiers.csv", index=False)
        with tab2:
            df_ct = pd.read_csv("data_controleurs.csv") if os.path.exists("data_controleurs.csv") else pd.DataFrame(columns=["Nom"])
            e_ct = st.data_editor(df_ct, num_rows="dynamic", key="ed_ct", use_container_width=True)
            if st.button("Sauvegarder Personnel"): e_ct.to_csv("data_controleurs.csv", index=False)

        with tab3: # ONGLET STRUCTURE
            st.subheader("📐 Éditeur de Structure VRD (Google Sheets)")
            
            # On affiche le tableau éditable
            if "df_config" in st.session_state:
                df_edite = st.data_editor(st.session_state.df_config, num_rows="dynamic", use_container_width=True)

                if st.button("💾 Sauvegarder les modifications sur Google Sheets"):
                    try:
                        client = connecter_drive()
                        # ATTENTION : Remplace par le nom exact de ton fichier Google Sheets
                        sh = client.open("Configuration_Questions").sheet1
                        sh.clear()
                        # Mise à jour du fichier en ligne
                        sh.update([df_edite.columns.values.tolist()] + df_edite.values.tolist())
                        st.session_state.df_config = df_edite
                        st.success("✅ Configuration mise à jour sur Google Sheets !")
                    except Exception as e:
                        st.error(f"Erreur de sauvegarde : {e}")
            # 4. SÉCURITÉ
        with tab4:
            st.subheader("🔑 Changer le mot de passe")
            nouveau_mdp = st.text_input("Nouveau mot de passe", type="password")
            confirmation = st.text_input("Confirmer le mot de passe", type="password")
    
            if st.button("💾 Enregistrer le nouveau mot de passe"):
                if nouveau_mdp == confirmation and len(nouveau_mdp) >= 4:
            # ON ÉCRASE LE FICHIER
                    with open("admin_pwd.txt", "w", encoding="utf-8") as f:
                        f.write(nouveau_mdp)
            
                    st.success("✅ Mot de passe mis à jour dans le système !")
            # ON FORCE LA DÉCONNEXION pour tester le nouveau mdp
                    st.session_state.auth_admin = False
                    st.info("Déconnexion automatique... Veuillez vous reconnecter avec le nouveau code.")
                    st.rerun()
                else:
                    t.error("Les mots de passe ne correspondent pas ou sont trop courts (min 4 car.).")