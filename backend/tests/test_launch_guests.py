from app.services import launch


async def test_guest_allowed_while_closed():
    await launch.set_open(False)
    try:
        await launch.set_guests(set())
        assert not await launch.allowed(555111)
        await launch.set_guests({555111})
        assert await launch.allowed(555111)
        assert not await launch.allowed(555222)  # boshqalarga hamon yopiq
        await launch.set_guests(set())
        assert not await launch.allowed(555111)
    finally:
        await launch.set_open(True)
