from python_bitvavo_api.bitvavo import Bitvavo


def bitvavo(config: dict) -> Bitvavo:
    """
    Initialiseert de Bitvavo WebSocket API client.
    """
    client = Bitvavo({
        'APIKEY': config.get('API_KEY'),
        'APISECRET': config.get('API_SECRET'),
        'RESTURL': config.get('RESTURL', 'https://api.bitvavo.com/v2'),
        'WSURL': config.get('WSURL', 'wss://ws.bitvavo.com/v2/'),
        'ACCESSWINDOW': config.get('ACCESSWINDOW', 10000),
        'DEBUGGING': config.get('DEBUGGING', False)
    })

