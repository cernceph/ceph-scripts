# Run with: pytest tools/upmap
#
# Use importlib since we can't import a module that contains a hyphen
import importlib
import pytest

upmap_remapped = importlib.import_module('upmap-remapped')

# osd, host, rack and root as ceph numbers them by default
OSD, HOST, RACK, ROOT = 0, 1, 3, 11

# 3 racks of 3 hosts of 2 osds: osds 0..5 in rack0, 6..11 in rack1, 12..17 in rack2
def crush_dump():
  buckets = [{"id": -1, "name": "default", "type_id": ROOT,
              "items": [{"id": -2}, {"id": -3}, {"id": -4}]}]
  for rack in range(3):
    rack_id = -2 - rack
    host_ids = [-5 - rack * 3 - h for h in range(3)]
    buckets.append({"id": rack_id, "name": "rack%d" % rack, "type_id": RACK,
                    "items": [{"id": h} for h in host_ids]})
    for h, host_id in enumerate(host_ids):
      osds = [rack * 6 + h * 2, rack * 6 + h * 2 + 1]
      buckets.append({"id": host_id, "name": "host%d" % (rack * 3 + h),
                      "type_id": HOST, "items": [{"id": o} for o in osds]})
  # a shadow bucket of the per-device-class tree, which has to be ignored
  buckets.append({"id": -100, "name": "default~ssd", "type_id": ROOT, "items": []})
  return {
    "types": [{"name": "osd", "type_id": OSD}, {"name": "host", "type_id": HOST},
              {"name": "rack", "type_id": RACK}, {"name": "root", "type_id": ROOT}],
    "buckets": buckets,
    "rules": [
      {"rule_id": 0, "steps": [{"op": "take"},
                               {"op": "chooseleaf_firstn", "type": "host"},
                               {"op": "emit"}]},
      {"rule_id": 1, "steps": [{"op": "take"},
                               {"op": "chooseleaf_firstn", "type": "rack"},
                               {"op": "emit"}]},
      {"rule_id": 2, "steps": [{"op": "take"},
                               {"op": "choose_indep", "type": "rack"},
                               {"op": "chooseleaf_indep", "type": "host"},
                               {"op": "emit"}]},
    ],
  }

def osd_dump():
  return {"pools": [{"pool": 1, "crush_rule": 0}, {"pool": 2, "crush_rule": 1},
                    {"pool": 3, "crush_rule": 2}]}

@pytest.fixture
def cluster(monkeypatch):
  """An 18 osd cluster, all of them in, up and weighted the same."""
  for name in ('PARENT', 'BUCKET_TYPE', 'CHILDREN', 'RULE_DOMAIN', 'POOL_RULE',
               '_domain_of', '_domain_osds'):
    monkeypatch.setattr(upmap_remapped, name, type(getattr(upmap_remapped, name))())
  monkeypatch.setattr(upmap_remapped, 'OSDS', set(range(18)))
  monkeypatch.setattr(upmap_remapped, 'WEIGHT', dict((o, 1.0) for o in range(18)))
  monkeypatch.setattr(upmap_remapped, 'UP', set(range(18)))
  upmap_remapped.build_topology(crush_dump(), osd_dump())
  return upmap_remapped

def rack_of(osd):
  return osd // 6

def host_of(osd):
  return osd // 2


def test_build_topology(cluster):
  # the failure domain of a rule is the type its one choose step names
  assert cluster.RULE_DOMAIN[0] == HOST
  assert cluster.RULE_DOMAIN[1] == RACK
  # a rule which chooses racks and then hosts inside them is not modelled
  assert cluster.RULE_DOMAIN[2] is None
  assert cluster.POOL_RULE['2'] == 1
  # the shadow bucket is not part of the tree
  assert -100 not in cluster.PARENT.values()
  assert cluster.domain_of(7, RACK) == -3
  assert sorted(cluster.domains(RACK)[1][-3]) == [6, 7, 8, 9, 10, 11]


def test_reverse_upmap(cluster):
  # 'pg ls' reports the up set with the items already applied
  assert cluster.reverse_upmap([5, 2, 3], [{'from': 1, 'to': 5}]) == [1, 2, 3]
  assert cluster.reverse_upmap([5, 2, 4], [{'from': 1, 'to': 5},
                                           {'from': 3, 'to': 4}]) == [1, 2, 3]
  assert cluster.reverse_upmap([1, 2, 3], []) == [1, 2, 3]


def test_rotations(cluster):
  # two shards trading places, and a longer rotation
  assert cluster.rotations([1, 2], [2, 1]) == [0, 1]
  assert cluster.rotations([1, 2, 3], [3, 1, 2]) == [0, 1, 2]
  # a chain is not a rotation: vacate 1 first, then fill it
  assert cluster.rotations([1, 2], [3, 1]) == []
  assert cluster.rotations([1, 2, 3], [1, 2, 3]) == []
  # the rotation is reported, the chain leading into it is not
  assert cluster.rotations([1, 2, 3], [4, 3, 2]) == [1, 2]


def test_target_is_acting_when_the_rule_still_allows_it(cluster):
  # adding or removing hardware: the acting set is a placement crush allows, so
  # the script keeps behaving exactly as it did
  assert cluster.pick_target('1.0', [1, 8, 14], [0, 8, 14], HOST) == [0, 8, 14]
  assert cluster.pick_target('1.0', [1, 8, 14], [0, 8, 14], RACK) == [0, 8, 14]
  # and when the failure domain of the rule is unknown, always
  assert cluster.pick_target('1.0', [1, 2, 3], [0, 1, 2], None) == [0, 1, 2]


def test_target_keeps_what_the_new_failure_domain_allows(cluster):
  # host -> rack: the acting set has all three shards in rack0, so two of them
  # have to move and the third stays where it is
  target = cluster.pick_target('1.7', [1, 8, 14], [0, 2, 4], RACK)
  assert target[0] == 0                       # kept: no other shard in rack0
  assert target[1:] == [8, 14]                # crush's own picks, and allowed
  assert sorted(rack_of(o) for o in target) == [0, 1, 2]


def test_target_replaces_what_it_cannot_keep(cluster):
  # crush's pick for the second position is in rack0 as well, so it cannot be
  # used either and the shard goes to a free rack
  target = cluster.pick_target('1.7', [1, 3, 14], [0, 2, 16], RACK)
  assert target[0] == 0                       # kept
  assert target[2] == 16                      # kept
  assert rack_of(target[1]) == 1              # the only rack left
  assert cluster.usable(target[1])


def test_target_spreads_the_forced_moves(cluster):
  # every pg of the pool is in the same situation; the osds they are forced onto
  # should not all be the same one
  picked = set()
  for ps in range(32):
    target = cluster.pick_target('1.%x' % ps, [0, 1, 2], [0, 1, 2], RACK)
    assert sorted(rack_of(o) for o in target) == [0, 1, 2]
    picked.update(target[1:])
  assert len(picked) > 4


def test_target_is_stable(cluster):
  first = cluster.pick_target('1.7', [1, 3, 14], [0, 2, 4], RACK)
  assert cluster.pick_target('1.7', [1, 3, 14], [0, 2, 4], RACK) == first


def test_target_avoids_osds_which_are_down(cluster, monkeypatch):
  monkeypatch.setattr(cluster, 'UP', set(range(18)) - set([8, 9, 10, 11]))
  monkeypatch.setattr(cluster, '_domain_osds', {})
  target = cluster.pick_target('1.7', [1, 8, 14], [0, 2, 4], RACK)
  assert target[0] == 0
  assert target[1] in (6, 7)                  # the osds of rack1 which are up
  assert target[2] == 14


def test_target_gives_up_when_the_rule_cannot_be_satisfied(cluster):
  # four shards to place over three racks
  assert cluster.pick_target('2.0', [0, 1, 2, 3], [0, 1, 2, 3], RACK) is None


def test_target_breaks_rotations(cluster):
  # both acting osds are allowed, but each sits where the other one is in the up
  # set, which pg-upmap-items cannot express
  up, acting = [2, 0], [0, 2]
  assert cluster.rotations(up, acting) == [0, 1]
  target = cluster.pick_target('3.1', up, acting, HOST)
  assert cluster.rotations(up, target) == []
  # one shard was kept, the other moved off the pg instead of going back to crush
  assert len(set(target) & set(acting)) == 1
  assert len(set(host_of(o) for o in target)) == 2
  assert cluster.gen_upmap(up, target) != []


def test_target_accepts_a_rotation_it_cannot_break(cluster, monkeypatch):
  # only two hosts have a usable osd, and both are already in the pg, so there
  # is nowhere to move a shard to
  monkeypatch.setattr(cluster, 'UP', set([0, 2]))
  monkeypatch.setattr(cluster, '_domain_osds', {})
  up, acting = [2, 0], [0, 2]
  assert cluster.pick_target('3.1', up, acting, HOST) == up


def test_gen_upmap_replicated(cluster, monkeypatch):
  # only the set matters: vacate what does not belong, fill what is missing
  assert cluster.gen_upmap([0, 8, 14], [0, 8, 15], replicated=True) == [(14, 15)]
  # the same set in another order needs no mapping at all
  assert cluster.gen_upmap([2, 0], [0, 2], replicated=True) == []
  # never map onto an osd which is out
  monkeypatch.setitem(cluster.WEIGHT, 15, 0)
  assert cluster.gen_upmap([0, 8, 14], [0, 8, 15], replicated=True) == []
  # nor onto one which is down
  monkeypatch.setitem(cluster.WEIGHT, 15, 1.0)
  monkeypatch.setattr(cluster, 'UP', set(range(18)) - set([15]))
  assert cluster.gen_upmap([0, 8, 14], [0, 8, 15], replicated=True) == []


def test_gen_upmap_erasure_is_ordered(cluster, monkeypatch):
  # the cases of #44, which this has to keep getting right
  monkeypatch.setattr(cluster, 'OSDS', set(range(16)))
  monkeypatch.setattr(cluster, 'WEIGHT', dict((o, 10.0) for o in range(16)))
  monkeypatch.setattr(cluster, 'UP', set(range(16)))
  gen_upmap = cluster.gen_upmap
  assert gen_upmap([2, 11, 5, 9, 15, 12], [2, 11, 5, 9, 14, 12]) == [(15, 14)]
  assert gen_upmap([4, 14, 10, 3, 7, 8], [9, 13, 2, 15, 5, 11]) == \
    [(4, 9), (14, 13), (10, 2), (3, 15), (7, 5), (8, 11)]
  assert gen_upmap([6, 12, 10, 0, 2, 9], [6, 12, 9, 0, 2, 4]) == [(9, 4), (10, 9)]
  assert gen_upmap([3, 4, 12, 6, 11, 0], [6, 14, 12, 4, 11, 0]) == \
    [(4, 14), (6, 4), (3, 6)]
  assert gen_upmap([7, 1, 12, 2, 15, 9], [7, 0, 4, 12, 9, 2]) == \
    [(1, 0), (12, 4), (2, 12), (9, 2), (15, 9)]
  # a rotation has no valid order
  assert gen_upmap([9, 4, 7, 10, 14, 2], [9, 7, 4, 10, 14, 2]) == []
