import cv2
import tkinter as tk
from tkinter import Label, Canvas, Frame, Scrollbar
from PIL import Image, ImageTk
from google.cloud import vision
from google.oauth2 import service_account
import threading
import requests
import json

# Ruta al archivo JSON de credenciales, usa el tuyo propio
GOOGLE_CREDENTIALS_PATH = "clave/tu_archivo"

# Cargar las credenciales desde el archivo
with open(GOOGLE_CREDENTIALS_PATH, "r") as credentials_file:
    credentials_dict = json.load(credentials_file)

# Crear credenciales desde el diccionario
credentials = service_account.Credentials.from_service_account_info(credentials_dict)

# Crear cliente de Google Vision API
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# Configurar Ollama API (Lo usamos para generar la sinopsis del libro)
OLLAMA_URL = "http://172.30.12.198:11434/api/generate"

# Función para identificar el título del libro mediante OCR
def identify_book_by_cover(image_path):
    with open(image_path, "rb") as image_file:
        content = image_file.read()

    # Usar Google Vision para detectar el texto
    image = vision.Image(content=content)

    # Almacenar el texto detectado
    response = vision_client.text_detection(image=image)

    # Si no se detecta texto la lista estará vacía
    if response.text_annotations:
        # El primer elemento suele ser el texto más relevante (título del libro)
        return response.text_annotations[0].description.strip()
    # Aprueba de fallos
    return "Título no identificado"

# Función para generar la sinopsis del libro usando Ollama
def generate_synopsis(book_title):
    # Conexión a Ollama
    payload = {
        "prompt": f"Proporciona un resumen del siguiente libro: {book_title}",
        "model": "llama3.1",
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(OLLAMA_URL, json=payload, headers=headers, stream=True)
        response.raise_for_status()

        texto_completo = ""
        for line in response.iter_lines():
            if line:
                fragmento = json.loads(line.decode('utf-8'))
                texto_completo += fragmento.get("response", "")
                if fragmento.get("done", False):
                    break
        return texto_completo
    except requests.exceptions.RequestException as e:
        return f"Error al conectar con Ollama: {e}"

# Clase principal para la interfaz gráfica
class BookRecognitionApp:
    def __init__(self, root):
        # Ventana principal
        self.root = root
        self.root.title("Reconocimiento de Libros por Portada")

        # Crear un marco para la cámara
        self.camera_frame = Frame(root)
        self.camera_frame.pack(fill=tk.X, pady=5)

        self.video_label = Label(self.camera_frame)
        self.video_label.pack()

        # Crear un label para el título
        self.title_label = Label(root, text="Título del libro: ---", font=("Arial", 16))
        self.title_label.pack(pady=5)

        # Crear un contenedor de desplazamiento para la sinopsis
        self.scroll_canvas = Canvas(root)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.scrollbar = Scrollbar(root, orient=tk.VERTICAL, command=self.scroll_canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scroll_frame = Frame(self.scroll_canvas)
        self.scroll_canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scroll_frame.bind("<Configure>", lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all")))

        self.synopsis_label = Label(self.scroll_frame, text="Sinopsis: ---", font=("Arial", 12), wraplength=500, justify="left")
        self.synopsis_label.pack()

        # Crear un marco para los botones
        self.button_frame = Frame(root)
        self.button_frame.pack(pady=10)

        capture_button = tk.Button(self.button_frame, text="Identificar Libro", command=self.process_frame)
        capture_button.pack(side=tk.LEFT, padx=5)

        quit_button = tk.Button(self.button_frame, text="Salir", command=self.stop)
        quit_button.pack(side=tk.RIGHT, padx=5)

        # Configurar la cámara
        self.cap = cv2.VideoCapture(0)
        self.running = True

        # Hilo para actualizar la cámara
        self.update_video()

    def update_video(self):
        if self.running:
            ret, frame = self.cap.read()
            if ret:
                # Convertir la imagen para Tkinter
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

            self.root.after(10, self.update_video)

    def capture_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Guardar el fotograma capturado
            image_path = "captured_frame.jpg"
            cv2.imwrite(image_path, frame)
            return image_path

    def process_frame(self):
        image_path = self.capture_frame()

        # Identificar libro y generar sinopsis en un hilo aparte
        def process():
            book_title = identify_book_by_cover(image_path)
            self.title_label.config(text=f"Título del libro: {book_title}")

            if book_title != "Título no identificado":
                synopsis = generate_synopsis(book_title)
                self.synopsis_label.config(text=f"Sinopsis: {synopsis}")
            else:
                self.synopsis_label.config(text="Sinopsis: No se encontró información del libro")

        threading.Thread(target=process).start()

    def stop(self):
        self.running = False
        self.cap.release()
        self.root.quit()

# Configurar la aplicación principal
if __name__ == "__main__":
    root = tk.Tk()
    app = BookRecognitionApp(root)
    root.mainloop()
