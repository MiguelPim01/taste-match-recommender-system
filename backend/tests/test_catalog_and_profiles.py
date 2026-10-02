from fastapi.testclient import TestClient


def test_yelp_profiles_are_seeded_in_id_order(client):
    profiles = client.get("/api/users").json()

    assert [(profile["id"], profile["display_name"]) for profile in profiles] == \
        [("yelp-a", "Perfil Yelp 001"), ("yelp-b", "Perfil Yelp 002")]


def test_seeding_twice_keeps_one_copy(make_app):
    for _ in range(2):
        with TestClient(make_app()) as client:
            totals = client.get("/api/health").json()

    assert (totals["restaurants"], totals["profiles"]) == (2, 2)


def test_new_profile_and_session(client):
    created = client.post("/api/users", json={"display_name": "  Ana  "})

    assert created.status_code == 201
    assert created.json()["display_name"] == "Ana" and created.json()["id"].startswith("app-")
    assert client.post("/api/session", json={"user_id": created.json()["id"]}).status_code == 200
    assert client.get("/api/session").json()["display_name"] == "Ana"
    assert client.delete("/api/session").status_code == 204
    assert client.get("/api/session").status_code == 401


def test_session_with_unknown_profile_is_rejected(client):
    assert client.post("/api/session", json={"user_id": "ninguem"}).status_code == 404


def test_catalog_search_category_and_sort(client):
    def ids(**params):
        return [restaurant["id"] for restaurant in client.get("/api/restaurants", params=params).json()["items"]]

    assert client.get("/api/restaurants").json()["total"] == 2
    assert ids() == ["r-pizza", "r-sushi"]
    assert ids(q="sushi") == ["r-sushi"]
    assert ids(category="Italian") == ["r-pizza"]
    assert ids(category="Ital") == []
    assert ids(sort="name") == ["r-sushi", "r-pizza"]


def test_restaurant_detail(client):
    restaurant = client.get("/api/restaurants/r-pizza").json()

    assert restaurant["categories"] == ["Pizza", "Italian", "Restaurants"]
    assert restaurant["stars"] == 4.5
    assert client.get("/api/restaurants/nao-existe").status_code == 404


def test_health_reports_kafka_and_projector(client, publisher):
    assert client.get("/api/health").json() == {"status": "ok", "kafka": True, "restaurants": 2, "profiles": 2,
                                                "projector": {"running": True, "events": 0, "lag": None}}

    publisher.down = True
    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_categories_skip_the_generic_ones(client):
    assert client.get("/api/restaurants/categories").json() == [
        {"name": "Italian", "count": 1}, {"name": "Japanese", "count": 1},
        {"name": "Pizza", "count": 1}, {"name": "Sushi Bars", "count": 1},
    ]
