from collections import deque


def menu():
    print("\n--- Sistema de Controle de Fila - Açougue Bom Preço ---")
    print("1 - Retirar Senha")
    print("2 - Chamar Próxima Senha")
    print("3 - Mostrar Fila Atual")
    print("4 - Sair")
    return input("Escolha uma opção: ")


# Inicialização da fila
fila = deque()
contador_senha = 0  # Movido para fora do loop para manter o contador


while True:
    opcao = menu()

    if opcao == '1':
        contador_senha += 1  # Incrementa o contador para cada nova senha
        senha = f"A{contador_senha}"
        fila.append(senha)  # Usar append() para adicionar à fila
        print(f"Senha {senha} retirada com sucesso!")


    elif opcao == '2':
        if fila:
            senha_chamada = fila.popleft()  # Chamar popleft() como método de fila
            print(f"Atenção! Senha chamada: {senha_chamada}")
        else:
            print("Fila vazia. Nenhuma senha para chamar.")


    elif opcao == '3':
        if fila:
            print("Fila atual de senhas: ", fila)  # Imprimir a fila diretamente
        else:
            print("Fila vazia.")


    elif opcao == '4':
        print("Sistema encerrado. Obrigado por utilizar!")
        break


    else:
        print("Opção inválida. Tente novamente.")
