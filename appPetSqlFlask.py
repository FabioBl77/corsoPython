import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, make_response
import mysql.connector
import csv
import io
from matplotlib import pyplot as plt
import pandas as pd

# Variabili username e password predefinite
USERNAME = "admin"
PASSWORD = "password"


app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Usato per firmare la sessione


# Funzione per gestire la connessione al database
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="",
        database="PyDb"
    )


@app.route('/combined_chart.png')
def plot_png():
    # Recupera i prodotti dal database
    mydb = get_db_connection()
    mycursor = mydb.cursor()
    mycursor.execute("SELECT * FROM prodottiPets")
    prodotti = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    # Estrai le etichette e vendite
    etichette = [row[1] for row in prodotti]  # Nome del prodotto (assumiamo che sia nella colonna 1)
    vendite = [row[7] for row in prodotti]  # Vendite (assumiamo che siano nella colonna 6)

    # Crea una figura con due subplot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

    # Aggiungi padding tra i subplot
    plt.subplots_adjust(left=0.1, right=0.9, top=0.8, bottom=0.3, wspace=0.2, hspace=0.2)

    # --- Grafico a barre ---
    ax1.bar(etichette, vendite, color='skyblue')
    ax1.set_title('Vendite per Prodotto (Grafico a Barre)', pad=30)
    ax1.set_ylabel('Vendite')
    ax1.tick_params(axis='x', rotation=45)  # Ruota le etichette per una migliore visibilità

    # --- Grafico a torta ---
    ax2.pie(vendite, labels=etichette, autopct='%1.1f%%', startangle=90, colors=['#ff9999', '#66b3ff', '#99ff99'])
    ax2.axis('equal')  # Per mantenere la torta circolare
    ax2.set_title('Distribuzione Vendite (Grafico a Torta)', pad = 30)

    # Salva la figura in memoria come PNG
    output = io.BytesIO()
    fig.savefig(output, format='png')
    plt.close(fig)
    output.seek(0)

    return make_response(output.getvalue(), 200, {'Content-Type': 'image/png'})


@app.route("/", methods=['GET', 'POST'])
def index():
    # Recupera i prodotti dal database
    mydb = get_db_connection()
    mycursor = mydb.cursor()
    mycursor.execute("SELECT * FROM prodottiPets")
    lista = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    # Inizializza il carrello nella sessione se non esiste
    if 'carrello' not in session:
        session['carrello'] = []

    # Se la richiesta è POST, gestisci l'aggiunta al carrello
    if request.method == 'POST':
        for key, value in request.form.items():
            if key.startswith('quantita-'):
                product_id = key.split('-')[1]  # Estrai l'ID del prodotto
                quantity = int(value)

                if quantity > 0:  # Solo se la quantità è maggiore di zero
                    # Recupera i dettagli del prodotto dal database
                    mydb = get_db_connection()
                    mycursor = mydb.cursor()
                    mycursor.execute("SELECT id, nome, prezzo FROM prodottiPets WHERE id = %s", (product_id,))
                    prodotto = mycursor.fetchone()
                    mycursor.close()
                    mydb.close()

                    if prodotto:
                        # Aggiungi o aggiorna il prodotto nel carrello
                        session['carrello'].append({
                            "id": prodotto[0],
                            "nome": prodotto[1],
                            "prezzo": float(prodotto[2]),  # Assicurati che il prezzo sia float
                            "quantita": quantity
                        })

        session.modified = True  # Segnala che la sessione è stata modificata
        return redirect("/")  # Redirect alla stessa pagina

    # Calcola il totale del carrello
    cart_total = sum(float(item['prezzo']) * item['quantita'] for item in session['carrello'])

    return render_template("vetrinaPet.html", lista=lista, cart=session['carrello'], cart_total=cart_total)


@app.route("/remove/<int:index>", methods=['POST'])
def removeCarrello(index):
    if 'carrello' in session and session['carrello'] is not None and len(session['carrello']) > 0:
        if index < len(session['carrello']):
            articolo_rimosso = session['carrello'].pop(index)
            print(f"Prodotto rimosso: {articolo_rimosso}")
        else:
            print("Indice non valido per rimuovere dal carrello.")
    else:
        print("Nessun carrello nella sessione.")
    return redirect("/")

@app.route("/prodAcquistati", methods=['GET'])
def prodAcquistati():
    # Controlla se ci sono acquisti nella sessione
    if 'carrello' in session and session['carrello']:
        acquisti = session['carrello']  # Recupera il carrello come acquisti

        # Connessione al database
        mydb = get_db_connection()
        mycursor = mydb.cursor()

        for acquisto in acquisti:
            prodotto_id = acquisto['id']
            quantita = acquisto['quantita']

            # Aggiorna pezzi e pezziVenduti nel database
            mycursor.execute("""
                UPDATE prodottiPets 
                SET pezzi = pezzi - %s, pezziVenduti = pezziVenduti + %s 
                WHERE id = %s
            """, (quantita, quantita, prodotto_id))

        mydb.commit()  # Commit delle modifiche
        mycursor.close()
        mydb.close()

        # Svuota il carrello
        session.pop('carrello', None)  # Rimuovi il carrello dalla sessione
    else:
        acquisti = []

    # Crea un resoconto degli acquisti
    resoconto = []
    totale_complessivo = 0  # Inizializza il totale complessivo

    for acquisto in acquisti:
        totale_parziale = acquisto['prezzo'] * acquisto['quantita']
        resoconto.append({
            'nome': acquisto['nome'],
            'prezzo': acquisto['prezzo'],
            'quantita': acquisto['quantita'],
            'totale_parziale': totale_parziale,
        })
        totale_complessivo += totale_parziale  # Somma al totale complessivo

    return render_template("storePet.html", acquisti=resoconto, totale=totale_complessivo)


@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == USERNAME and password == PASSWORD:
            session['user'] = username
            return redirect(url_for('gestore'))
        else:
            return "Credenziali non valide"

    return render_template("loginPetTemplate.html")


@app.route("/gestore", methods=['GET', 'POST'])
def gestore():
    if 'user' in session:
        mydb = get_db_connection()
        mycursor = mydb.cursor()

        if request.method == 'POST':
            categoriaP = request.form.get('categoriaP')
            if categoriaP == "tutte" or not categoriaP:
                mycursor.execute("SELECT * FROM prodottiPets")

            else:
                sql = "SELECT * FROM prodottiPets WHERE categoria = %s"
                mycursor.execute(sql, (categoriaP,))
        else:
            mycursor.execute("SELECT * FROM prodottiPets")

        lista = mycursor.fetchall()
        mycursor.execute("SELECT DISTINCT categoria FROM prodottiPets")
        listaS = [cat[0] for cat in mycursor.fetchall()]

        #Utilizzo della libreria pandas
        query = "SELECT * FROM prodottiPets"
        df = pd.read_sql(query, mydb)
        pd.set_option('display.max_columns', None)

        query = "SELECT id, nome, marca, pezzi, pezziVenduti  FROM prodottiPets"
        mycursor.execute(query)
        myresult1 = mycursor.fetchall()
        # Ottenere i nomi delle colonne
        column_names = [desc[0] for desc in mycursor.description]

        # Creare un DataFrame Pandas con i nomi delle colonne
        df = pd.DataFrame(myresult1, columns=column_names)
        print(column_names)
        print(df)
        sommaP = df['pezzi'].sum()
        sommaV = df['pezziVenduti'].sum()
        print(sommaP, sommaV)
        mediaP = df['pezzi'].mean()
        mediaV = df['pezziVenduti'].mean()
        print(mediaP, mediaV)
        new_row = {
            'id': "",  # Imposta su NaN o su un valore predefinito
            'nome': "SOMMA:",  # Imposta su NaN o su un valore predefinito
            'marca': "",  # Imposta su NaN o su un valore predefinito
            'pezzi': sommaP,  # Valore specificato
            'pezziVenduti': sommaV  # Valore specificato
        }
        new_row2 = {
            'id': "",  # Imposta su NaN o su un valore predefinito
            'nome': "MEDIA:",  # Imposta su NaN o su un valore predefinito
            'marca': "",  # Imposta su NaN o su un valore predefinito
            'pezzi': mediaP,  # Valore specificato
            'pezziVenduti': mediaV  # Valore specificato
        }

        ## Creare un DataFrame dalla nuova riga
        new_row_df = pd.DataFrame([new_row])
        new_row2_df = pd.DataFrame([new_row2])

        # Aggiungere la nuova riga usando pd.concat
        df = pd.concat([df, new_row_df], ignore_index=True)
        df = pd.concat([df, new_row2_df], ignore_index=True)

        # Calcolare il prodotto più venduto
        index_max = df['pezziVenduti'].idxmax()  # Ottieni l'indice del valore massimo
        # Calcolare il prodotto meno venduto
        index_max = df['pezziVenduti'].idxmin()  # Ottieni l'indice del valore minimo

        # Calcolare l'indice del prodotto più venduto, escludendo l'ultima riga
        index_max = df['pezziVenduti'][:-2].idxmax()  # Prende solo le righe fino all'ultima
        prodotto_piu_venduto = df.loc[index_max]
        prodottoMax = prodotto_piu_venduto['nome']

        index_min = df['pezziVenduti'][:-2].idxmin()
        prodotto_meno_venduto = df.loc[index_min]
        prodottoMin = prodotto_meno_venduto['nome']

        lista_prodotti = df.values.tolist()
        print(lista_prodotti)
        mycursor.close()
        mydb.close()
        return render_template("gestorePet.html", lista=lista, listaS=listaS, listaPandas=lista_prodotti, prodottoMax=prodottoMax, prodottoMin=prodottoMin)
    else:
        return redirect(url_for('login'))


@app.route("/process", methods=['POST'])
def process():
    nome = request.form['nome']
    marca = request.form['marca']
    prezzo = request.form['prezzo']
    categoria = request.form['categoria']
    url = request.form['url']
    pezzi = request.form['pezzi']

    mydb = get_db_connection()
    mycursor = mydb.cursor()
    sql = "INSERT INTO prodottiPets (nome, marca, prezzo, categoria, url, pezzi) VALUES (%s, %s, %s, %s, %s, %s)"
    val = (nome, marca, prezzo, categoria, url, pezzi)
    mycursor.execute(sql, val)
    mydb.commit()
    mycursor.close()
    mydb.close()
    return redirect(url_for('gestore'))


@app.route("/remove", methods=['POST'])
def remove():
    prod_id = request.form['prod']
    mydb = get_db_connection()
    mycursor = mydb.cursor()
    sql = "DELETE FROM prodottiPets WHERE id = %s"
    val = (prod_id,)
    mycursor.execute(sql, val)
    mydb.commit()
    mycursor.close()
    mydb.close()
    return redirect(url_for('gestore'))


@app.route("/updatePezzi", methods=['POST'])
def updatePezzi():
    prod_id = request.form['prodID']
    n_pezzi = request.form['Npezzi']

    mydb = get_db_connection()
    mycursor = mydb.cursor()
    sql = "UPDATE prodottiPets SET pezzi = pezzi + %s WHERE id = %s"
    val = (n_pezzi, prod_id)
    mycursor.execute(sql, val)
    mydb.commit()
    mycursor.close()
    mydb.close()
    return redirect(url_for('gestore'))


@app.route("/export_csv", methods=['GET'])
def export_csv():
    mydb = get_db_connection()
    mycursor = mydb.cursor()
    mycursor.execute("SELECT * FROM prodottiPets")
    myresult = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    file_csv = 'prodotti.csv'

    with open(file_csv, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['ID', 'Nome', 'Marca', 'Prezzo', 'Categoria', 'URL', 'Pezzi', 'pezziVenduti'])
        for row in myresult:
            writer.writerow(row)

    return send_file(file_csv, as_attachment=True)


@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route("/buy", methods=['POST'])
def buy():
    lista_quantita = request.form.getlist('quantita')
    lista_prodotti_id = request.form.getlist('prodotto_id')

    if 'carrello' not in session:
        session['carrello'] = []

    mydb = get_db_connection()
    mycursor = mydb.cursor()

    for i, quantita in enumerate(lista_quantita):
        if int(quantita) > 0:
            prodotto_id = lista_prodotti_id[i]
            mycursor.execute("SELECT id, nome, prezzo FROM prodottiPets WHERE id = %s", (prodotto_id,))
            prodotto = mycursor.fetchone()

            if prodotto:
                # Verifica se il prodotto è già nel carrello
                for item in session['carrello']:
                    if item['id'] == prodotto[0]:
                        item['quantita'] += int(quantita)
                        break
                else:
                    # Aggiungi nuovo prodotto al carrello
                    session['carrello'].append({
                        "id": prodotto[0],
                        "nome": prodotto[1],
                        "prezzo": float(prodotto[2]),  # Assicurati che il prezzo sia float
                        "quantita": int(quantita)
                    })

    mycursor.close()
    mydb.close()

    return redirect("/prodAcquistati")  # Reindirizza alla pagina di acquisto


@app.route("/carrello", methods=['GET'])
def carrello():
    carrello = session.get('carrello', [])
    cart_total = sum(item['prezzo'] * item['quantita'] for item in carrello)

    return render_template("carrelloPet.html", carrello=carrello, cart_total=cart_total)


@app.route("/confirm", methods=['POST'])
def confirm():
    if 'user' in session:
        try:
            items = request.get_json().get('items', [])
            if not items:
                return jsonify({"error": "Nessun articolo nel carrello."}), 400

            conn = get_db_connection()
            cursor = conn.cursor()
            totale = 0
            acquisti = []

            for item in items:
                prodotto_id = item['id']
                quantita = item['quantita']

                cursor.execute("SELECT nome, pezzi, prezzo FROM prodottiPets WHERE id = %s", (prodotto_id,))
                prodotto = cursor.fetchone()

                if prodotto:
                    if prodotto[1] >= quantita:
                        cursor.execute(""" 
                            UPDATE prodottiPets 
                            SET pezzi = pezzi - %s, pezziVenduti = pezziVenduti + %s 
                            WHERE id = %s
                        """, (quantita, quantita, prodotto_id))

                        totale += prodotto[2] * quantita
                        acquisti.append({
                            'nome': prodotto[0],
                            'prezzo': prodotto[2],
                            'quantita': quantita,
                            'totale_parziale': prodotto[2] * quantita
                        })
                    else:
                        return jsonify({"error": f"Quantità insufficiente per il prodotto ID: {prodotto_id}"}), 400
                else:
                    return jsonify({"error": f"Prodotto ID: {prodotto_id} non trovato"}), 400

            conn.commit()

            # Svuota il carrello dopo l'acquisto
            session.pop('carrello', None)  # Rimuovi il carrello dalla sessione

            return jsonify({"success": True, "acquisti": acquisti, "totale": totale})
        except Exception as e:
            return jsonify({"error": "Errore durante l'acquisto"}), 500
    else:
        return jsonify({"error": "Utente non autenticato"}), 403


if __name__ == "__main__":
    app.run(debug=True)
