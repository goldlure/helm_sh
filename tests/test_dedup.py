from check_once import normalize_url

def test_newest_seen_means_no_new_posts():
    posts = [
        {"link": normalize_url("https://example.com/new")},
        {"link": normalize_url("https://example.com/old")},
    ]

    last_seen = normalize_url("https://example.com/new")

    new_posts = []
    for p in posts:
        if p["link"] == last_seen:
            break
        new_posts.append(p)

    assert new_posts == []
