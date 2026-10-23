class ClaseHelloWord:
    def __init__(self, nombre="Mundo"):
        self.nombre = nombre

    def saludar(self):
        return f"¡Hola, {self.nombre}!"


if __name__ == "__main__":
    mensaje = ClaseHelloWord("Python")
    print(mensaje.saludar())
