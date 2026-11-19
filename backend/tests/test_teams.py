from tests.conftest import set_balance


async def _users(api, *ids, rank="mythic"):
    for i in ids:
        await set_balance(i, 0)
        await api(i).put("/arena/profile", {"nick": f"P{i}", "rank": rank, "lane": "gold", "region": "Xorazm"})


async def test_team_lifecycle_join_invite_kick_leave(api, ctx):
    await _users(api, 50, 51, 52, 53)
    r = await api(50).post("/arena/teams", {"name": "Xorazm guch", "tag": "xrz", "region": "Xorazm"})
    assert r.status_code == 200, r.text
    t = r.json()["team"]
    assert t["tag"] == "XRZ" and t["members"] == 1 and t["is_captain"] and t["avg_rank"] == "mythic"
    assert (await api(51).post("/arena/teams", {"name": "xorazm GUCH"})).status_code == 409  # nom band
    # qo'shilish so'rovi → sardor qabul qiladi
    assert (await api(51).post(f"/arena/teams/{t['id']}/join")).status_code == 200
    assert (await api(51).post(f"/arena/teams/{t['id']}/join")).status_code == 409
    my = (await api(50).get("/arena/teams/my")).json()
    rid = my["requests"][0]["id"]
    assert (await api(52).post(f"/arena/requests/{rid}", {"accept": True})).status_code == 403  # sardor emas
    my = (await api(50).post(f"/arena/requests/{rid}", {"accept": True})).json()
    assert my["team"]["members"] == 2
    assert any(uid == 51 and "qo'shildingiz" in txt for uid, txt, _ in ctx["sent"])
    # taklif → o'yinchi qabul qiladi
    assert (await api(50).post("/arena/teams/invite", {"user_id": 52})).status_code == 200
    inv = (await api(52).get("/arena/teams/my")).json()["invites"]
    assert inv[0]["team"]["name"] == "Xorazm guch"
    assert (await api(52).post(f"/arena/requests/{inv[0]['id']}", {"accept": True})).json()["team"]["members"] == 3
    # ro'yxat va qidiruv
    lst = (await api(53).get("/arena/teams?q=xrz&open=1")).json()
    assert lst[0]["members"] == 3 and lst[0]["free"] == 4 and lst[0]["captain"] == "P50"
    # chiqarish va sardor chiqib ketishi → sardorlik keyingisiga
    my = (await api(50).post("/arena/teams/kick", {"user_id": 52})).json()
    assert my["team"]["members"] == 2
    await api(50).post("/arena/teams/leave")
    my = (await api(51).get("/arena/teams/my")).json()
    assert my["team"]["is_captain"] and my["team"]["members"] == 1
    await api(51).post("/arena/teams/leave")
    assert (await api(53).get("/arena/teams")).json() == []
    # nom bo'shadi
    assert (await api(53).post("/arena/teams", {"name": "Xorazm guch"})).status_code == 200


async def test_posts_kinds_match_respond_and_respect(api, ctx):
    await _users(api, 60, 61)
    await _users(api, 62, rank="epic")
    # sherik e'loni, mos rank filtri
    r = await api(60).post("/arena/posts", {"kind": "duo", "lane": "Gold", "online": "20:00–24:00", "note": "Mythic push"})
    assert r.status_code == 200 and r.json()["author"]["nick"] == "P60" and r.json()["region"] == "Xorazm"
    assert len((await api(61).get("/arena/posts?kind=duo&match=1")).json()) == 1
    assert (await api(62).get("/arena/posts?kind=duo&match=1")).json() == []  # Epic ≠ Mythic
    assert len((await api(62).get("/arena/posts?kind=duo&region=Xorazm&lane=Gold")).json()) == 1
    # jamoasiz scrim va team e'loni — taqiqlangan
    assert (await api(61).post("/arena/posts", {"kind": "scrim"})).status_code == 409
    # javob → bog'lanish → hurmat
    assert (await api(62).post(f"/arena/rate/60", {"good": False})).status_code == 409  # bog'lanmagan
    pid = r.json()["id"]
    assert (await api(61).post(f"/arena/posts/{pid}/respond")).status_code == 200
    assert any(uid == 60 for uid, *_ in ctx["sent"])
    resp = (await api(61).post("/arena/rate/60", {"good": True})).json()
    assert resp["good"] == 1 and resp["pct"] == 100
    assert (await api(61).get("/arena/contacts")).json()[0]["my_rating"] is True
    # jamoa o'yinchi qidirmoqda → javob = qo'shilish so'rovi
    await api(60).post("/arena/teams", {"name": "ORCA"})
    tp = (await api(60).post("/arena/posts", {"kind": "team", "lane": "Roam"})).json()
    assert tp["team"]["name"] == "ORCA"
    assert (await api(62).post(f"/arena/posts/{tp['id']}/respond")).json()["text"].startswith("So'rov")
    assert (await api(60).get("/arena/teams/my")).json()["requests"][0]["user_id"] == 62


async def test_partner_signal(api, ctx):
    await _users(api, 70, 71)
    await _users(api, 72, rank="warrior")
    assert (await api(71).post("/arena/signal", {"enabled": True})).status_code == 200
    assert (await api(72).post("/arena/signal", {"enabled": True})).status_code == 200
    await set_balance(73, 0)
    assert (await api(73).post("/arena/signal", {"enabled": True})).status_code == 409  # rank yo'q
    ctx["sent"].clear()
    await api(70).post("/arena/posts", {"kind": "duo"})
    got = {uid for uid, txt, _ in ctx["sent"] if "Sherik signali" in txt}
    assert got == {71}
    assert (await api(71).get("/arena/search/meta")).json()["signal"] is True
