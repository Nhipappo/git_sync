import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает настроенный логгер для модуля.

    Параметры:
        name — обычно передаётся __name__ из вызывающего модуля,
               чтобы в логах было видно, какой файл пишет сообщение.

    Формат вывода: цветной префикс [INFO] + текст сообщения.
    Все логи идут в stdout (не в stderr), чтобы их можно было
    перехватывать в Docker/k8s через стандартный поток.

    Повторные вызовы с одним name возвращают тот же экземпляр
    (стандартное поведение logging.getLogger).
    """
    logging.basicConfig(
        level=logging.INFO,
        format='|\033[1;35m|\033[1;36m [INFO]\033[0m %(message)s',
        stream=sys.stdout
    )
    return logging.getLogger(name)
