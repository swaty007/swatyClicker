"""Built-in compatibility results from our own research (docs/research/lu4-input-methods.md)."""
from myclicker.domain.compatibility import Entry, Status

LU4 = "LU4"

BUILTIN_COMPATIBILITY = [
    Entry(LU4, "mouse.postmessage", Status.WORKS,
          "Клик по Game Macro (ячейка панели / окно Macro) — и в фоне. Окно в оконном режиме, не свёрнуто."),
    Entry(LU4, "mouse.sendmessage", Status.UNTESTED,
          "Кнопка интерфейса не нажалась (проверено только в безрамочном полноэкранном режиме)."),
    Entry(LU4, "mouse.sendinput_abs", Status.PARTIAL,
          "Game Macro и кнопки интерфейса — да; ячейка умения напрямую и клик по земле — нет. Нужен фокус."),
    Entry(LU4, "mouse.setcursor_sendinput", Status.PARTIAL, "Кнопки интерфейса — да; макросы не проверялись."),
    Entry(LU4, "mouse.mouse_event", Status.PARTIAL, "Кнопки интерфейса — да; макросы не проверялись."),
    Entry(LU4, "mouse.interception", Status.FAILS,
          "Драйвер установлен, но при запущенной игре не видит устройств (вероятно, глушит Active Anticheat)."),
    Entry(LU4, "key.postmessage", Status.FAILS, "F12 не срабатывает ни в фоне, ни в активном окне."),
    Entry(LU4, "key.sendmessage", Status.FAILS, "F12 не срабатывает."),
    Entry(LU4, "key.postmessage_char", Status.UNTESTED, ""),
    Entry(LU4, "key.sendinput_vk", Status.FAILS, "F12 не срабатывает (в т.ч. после клика в окно)."),
    Entry(LU4, "key.sendinput_scan", Status.FAILS, "F12 не срабатывает (в т.ч. с удержанием 250 мс)."),
    Entry(LU4, "key.keybd_event", Status.FAILS, "F12 не срабатывает."),
    Entry(LU4, "key.interception", Status.FAILS,
          "Драйвер установлен, но при запущенной игре не видит устройств (вероятно, глушит Active Anticheat)."),
]
