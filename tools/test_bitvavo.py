import json
import time
# ✅ Correcte import van de Bitvavo API-client
from bitvavo.Bitvavo import Bitvavo

# ✅ Vul hier je API-sleutels in of laad ze uit een beveiligde omgeving
API_KEY=""
API_SECRET=""

bitvavo = Bitvavo({
    "APIKEY": API_KEY,
    "APISECRET": API_SECRET,
    "ACCESSWINDOW": 10000  # Zorgt voor tijdssynchronisatie
})


def test_api_authentication():
    """Test API-authenticatie en accountinformatie ophalen."""
    try:
        print("📡 Testing API Authentication...")
        account_info = bitvavo.account()
        print("✅ API Authentication Successful!")
        print(json.dumps(account_info, indent=4))
    except Exception as e:
        print(f"❌ API authentication failed: {e}")


def test_place_order():
    """Plaats een testorder met een kleine hoeveelheid en gebruik 'amountQuote' voor market buy."""
    try:
        print("📡 Testing order placement...")

        # ✅ Kies een testmarkt en kleine hoeveelheid
        market = "ADA-EUR"
        order = bitvavo.placeOrder(
            market, "buy", "market", {
                "amountQuote": "5"}  # ✅ Koop 5 EUR aan ADA
        )
        print("✅ Order placed successfully!")
        print(json.dumps(order, indent=4))
        return order.get("orderId", None)
    except Exception as e:
        print(f"❌ Order placement failed: {e}")
        return None


def test_get_orders():
    """Check of orders kunnen worden opgehaald."""
    try:
        print("📡 Testing fetching last orders...")
        orders = bitvavo.getOrders({"market": "ADA-EUR", "limit": 3})
        print("✅ Fetched orders successfully!")
        print(json.dumps(orders, indent=4))
    except Exception as e:
        print(f"❌ Failed to fetch orders: {e}")


def test_get_fills(order_id):
    """Test het ophalen van fills voor een order."""
    if not order_id:
        print("⚠️ No order ID provided, skipping fills check.")
        return
    try:
        print(f"📡 Fetching fills for order: {order_id}...")
        fills = bitvavo.getFills({"orderId": order_id})
        print("✅ Fills received:")
        print(json.dumps(fills, indent=4))
    except Exception as e:
        print(f"❌ Failed to fetch fills: {e}")


def main():
    """Voer alle tests uit."""
    print("🚀 Running Bitvavo API Test Script...\n")

    # 1️⃣ Test API-authenticatie
    test_api_authentication()

    # 2️⃣ Test het plaatsen van een order
    order_id = test_place_order()

    # Wacht een paar seconden om de order te laten verwerken
    time.sleep(3)

    # 3️⃣ Test het ophalen van orderhistorie
    test_get_orders()

    # 4️⃣ Test het ophalen van fills voor de laatste order
    test_get_fills(order_id)

    print("\n🎉 All tests completed!")


if __name__ == "__main__":
    main()
