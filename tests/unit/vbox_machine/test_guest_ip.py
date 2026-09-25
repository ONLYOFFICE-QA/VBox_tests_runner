from frameworks.VboxMachine.guest_ip import pick_reachable_guest_ip


class TestPickReachableGuestIp:
    def test_skips_nat_and_prefers_hostonly(self):
        """NAT 10.0.2.15 is not reachable from the host; host-only wins."""
        assert pick_reachable_guest_ip(['10.0.2.15', '192.168.56.101']) == '192.168.56.101'

    def test_returns_none_when_only_nat(self):
        """wait_up() seeing only NAT must not be used for SSH."""
        assert pick_reachable_guest_ip(['10.0.2.15']) is None

    def test_skips_loopback_and_link_local(self):
        assert pick_reachable_guest_ip(['127.0.0.1', '169.254.1.1', '192.168.56.10']) == '192.168.56.10'

    def test_falls_back_to_bridged_when_no_hostonly(self):
        assert pick_reachable_guest_ip(['10.0.2.15', '192.168.3.27']) == '192.168.3.27'

    def test_ignores_invalid_addresses(self):
        assert pick_reachable_guest_ip(['', 'not-an-ip', '192.168.56.7']) == '192.168.56.7'

    def test_empty_list(self):
        assert pick_reachable_guest_ip([]) is None
