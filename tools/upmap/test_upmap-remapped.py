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
      {"rule_id": 3, "steps": [{"op": "take"},
                               {"op": "chooseleaf_indep", "type": "osd"},
                               {"op": "emit"}]},
    ],
  }

def osd_dump():
  return {"pools": [{"pool": 1, "crush_rule": 0}, {"pool": 2, "crush_rule": 1},
                    {"pool": 3, "crush_rule": 2}, {"pool": 4, "crush_rule": 3}]}

# The same cluster with device classes: the even osd of every host is an hdd, the
# odd one an ssd, and rule 1 becomes 'take default class hdd; chooseleaf indep 0
# type rack'.  Like a real crush dump, it carries the default~hdd shadow tree
# that take step points at.
def crush_dump_with_classes():
  crush = crush_dump()
  crush['buckets'] = [b for b in crush['buckets'] if '~' not in b['name']]
  for b in list(crush['buckets']):
    shadow = {'id': b['id'] - 100, 'name': b['name'] + '~hdd', 'type_id': b['type_id']}
    if b['type_id'] == HOST:
      shadow['items'] = [i for i in b['items'] if i['id'] % 2 == 0]
    else:
      shadow['items'] = [{'id': i['id'] - 100} for i in b['items']]
    crush['buckets'].append(shadow)
  crush['rules'][1]['steps'] = [{"op": "take", "item": -101, "item_name": "default~hdd"},
                                {"op": "chooseleaf_indep", "type": "rack"},
                                {"op": "emit"}]
  return crush

def reset(cluster, crush):
  for name in ('PARENT', 'BUCKET_TYPE', 'CHILDREN', 'RULE_DOMAIN', 'RULE_ROOT',
               'POOL_RULE', '_domain_of', '_domain_osds', '_root_osds'):
    getattr(cluster, name).clear()
  cluster.build_topology(crush, osd_dump())

@pytest.fixture
def cluster(monkeypatch):
  """An 18 osd cluster, all of them in, up and weighted the same."""
  for name in ('PARENT', 'BUCKET_TYPE', 'CHILDREN', 'RULE_DOMAIN', 'RULE_ROOT',
               'POOL_RULE', '_domain_of', '_domain_osds', '_root_osds'):
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
  # nor is one whose failure domain is the osd
  assert cluster.RULE_DOMAIN[3] is None
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
  # crush now picks 7 itself, so the mon skipped the item 5 -> 7 and 5 is still
  # in the pg: undoing it would put 5 in the pg twice
  assert cluster.reverse_upmap([7, 5, 9], [{'from': 5, 'to': 7}]) == [7, 5, 9]
  # a skipped item does not stop the ones around it from being undone
  assert cluster.reverse_upmap([7, 5, 4], [{'from': 5, 'to': 7},
                                           {'from': 3, 'to': 4}]) == [7, 5, 3]


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


NONE = 2147483647   # how 'pg ls' shows a shard without an osd

def test_target_is_acting_with_a_failure_domain_down(cluster, monkeypatch):
  # ec 6+3 over the 9 hosts, and host0 down: the pool has one failure domain
  # fewer than shards, and every pg is missing a shard.  A pg remapped within
  # host5 by an osd change is still mapped back the way master does it.
  monkeypatch.setattr(cluster, 'UP', set(range(18)) - set([0, 1]))
  monkeypatch.setattr(cluster, '_domain_osds', {})
  up     = [2, 4, 6, 8, 11, 12, 14, 16, NONE]
  acting = [2, 4, 6, 8, 10, 12, 14, 16, NONE]
  target = cluster.pick_target('1.7', up, acting, HOST)
  assert target == acting
  assert cluster.gen_upmap(up, target) == [(11, 10)]


def test_target_moves_what_it_must_with_a_failure_domain_down(cluster, monkeypatch):
  # the same pool, but two acting shards share host5 after a rule change: the
  # pg is fixed on its own, and the shard crush could not place stays unplaced
  monkeypatch.setattr(cluster, 'UP', set(range(18)) - set([0, 1]))
  monkeypatch.setattr(cluster, '_domain_osds', {})
  up     = [2, 4, 6, 8, 10, 12, 14, 16, NONE]
  acting = [2, 4, 6, 8, 10, 11, 14, 16, NONE]
  target = cluster.pick_target('1.7', up, acting, HOST)
  assert target == [2, 4, 6, 8, 10, 12, 14, 16, NONE]
  assert cluster.gen_upmap(up, target) == []


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


def test_target_is_acting_on_an_osd_failure_domain(cluster):
  # rule 3 separates the pg over osds: its domain is unknown, so the pg gets
  # the acting set and the mapping master would make
  up, acting = [0, 1, 2, 3], [0, 1, 2, 5]
  target = cluster.pick_target('4.0', up, acting, cluster.RULE_DOMAIN[3])
  assert target == acting
  assert cluster.gen_upmap(up, target) == [(3, 5)]


def test_target_stays_in_the_device_class_of_the_rule(cluster):
  reset(cluster, crush_dump_with_classes())
  root = cluster.RULE_ROOT[1]
  assert root == -101
  hdd = set(o for o in range(18) if o % 2 == 0)
  # the failure domain is still read from the real tree
  assert cluster.domain_of(6, RACK) == -3
  for ps in range(256):
    # acting has the shards of rack0 and rack1 swapped, so the rotation breaker
    # moves one of them to another osd of its rack: it must be another hdd
    target = cluster.pick_target('2.%x' % ps, [6, 0, 12], [0, 6, 12], RACK, root=root)
    assert set(target) <= hdd
    assert sorted(rack_of(o) for o in target) == [0, 1, 2]
  # and a forced move off a shared rack goes to an hdd as well
  for ps in range(64):
    target = cluster.pick_target('2.%x' % ps, [0, 6, 12], [0, 2, 4], RACK, root=root)
    assert target[0] == 0
    assert set(target) <= hdd


def test_target_does_not_keep_an_osd_outside_the_rule(cluster):
  # a pool moved from an ssd rule to the hdd rule 1: its ssd shards cannot stay,
  # even where their rack would allow it
  reset(cluster, crush_dump_with_classes())
  target = cluster.pick_target('2.0', [0, 6, 12], [1, 7, 12], RACK,
                               root=cluster.RULE_ROOT[1])
  assert target == [0, 6, 12]


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


def test_weighted_choice(cluster):
  # each item - an osd or a bucket id - is picked in proportion to its weight
  weight = {1: 1.0, 3: 3.0}
  picks = [cluster.weighted_choice([1, 3], weight.get, '1.%x' % ps, 0, 0)
           for ps in range(2000)]
  assert 400 < picks.count(1) < 600         # a quarter of them
  # every item draws its own straw: taking one away, or making it heavier, only
  # moves the picks it had or gets
  weight = {1: 1.0, 2: 2.0, 3: 3.0}
  def picks_with(items, weight):
    return [cluster.weighted_choice(items, weight.get, '1.%x' % ps, 0, 0)
            for ps in range(2000)]
  before = picks_with([1, 2, 3], weight)
  without_3 = picks_with([1, 2], weight)
  assert all(x == y for x, y in zip(before, without_3) if x != 3)
  heavier_3 = picks_with([1, 2, 3], dict(list(weight.items()) + [(3, 6.0)]))
  assert all(y == 3 for x, y in zip(before, heavier_3) if x != y)
  assert heavier_3.count(3) > before.count(3)


def test_spread_takes_any_pgid(cluster):
  # a pgid it cannot read still gets a number: the one of pg 0.0
  for pgid in ('1', '1.3.1', 'x.y'):
    assert cluster.spread(pgid, 1) == cluster.spread('0.0', 1)
  # and the draw of 0 it can come to still makes a straw
  assert cluster.spread('x.y', 0) == 0
  assert cluster.weighted_choice([0], {0: 1.0}.get, 'x.y', 0, 0) == 0


def test_target_spreads_the_forced_moves_by_weight(cluster, monkeypatch):
  # a size 2 pool whose shards share rack0: one stays, the other goes to rack1
  # or rack2.  rack1 weighs ten times what rack2 does, and osd 6 half of rack1,
  # so the moves should go there in about those proportions.
  weight = dict((o, 1.0) for o in range(18))
  weight[6] = 5.0
  weight.update((o, 1.0 / 6) for o in range(12, 18))
  monkeypatch.setattr(cluster, 'WEIGHT', weight)
  picks = [cluster.pick_target('1.%x' % ps, [0, 1], [0, 2], RACK,
                               replicated=True)[1]
           for ps in range(1000)]
  to_rack2 = [o for o in picks if rack_of(o) == 2]
  to_rack1 = [o for o in picks if rack_of(o) == 1]
  assert 50 < len(to_rack2) < 140             # 1/11 of them
  assert 0.4 < to_rack1.count(6) / len(to_rack1) < 0.6
  assert all(rack_of(o) != 0 for o in picks)


def test_target_breaks_rotations_by_weight(cluster, monkeypatch):
  # the rotation breaker moves a shard onto an osd outside the pg, picking the
  # host and the osd by weight too: host8 weighs 8 of the 21 the free hosts
  # have, and osd 16 three quarters of host8
  weight = dict((o, 1.0) for o in range(18))
  weight[16], weight[17] = 6.0, 2.0
  monkeypatch.setattr(cluster, 'WEIGHT', weight)
  moved = []
  for ps in range(1000):
    target = cluster.pick_target('3.%x' % ps, [2, 0], [0, 2], HOST)
    assert cluster.rotations([2, 0], target) == []
    moved += [o for o in target if o not in (0, 2)]
  assert len(moved) == 1000
  to_host8 = [o for o in moved if host_of(o) == 8]
  assert 300 < len(to_host8) < 460            # 8/21 of them
  assert 0.65 < to_host8.count(16) / len(to_host8) < 0.85


def test_target_spreads_the_pools_apart(cluster):
  # pgs of two pools with the same placement seed, in the same situation, do not
  # all make the same choice
  differ = 0
  for ps in range(256):
    assert cluster.spread('1.%x' % ps, 1) != cluster.spread('2.%x' % ps, 1)
    a = cluster.pick_target('1.%x' % ps, [0, 1], [0, 2], RACK, replicated=True)
    b = cluster.pick_target('2.%x' % ps, [0, 1], [0, 2], RACK, replicated=True)
    differ += a != b
  assert differ > 192


def test_target_weighs_only_the_osds_it_can_use(cluster, monkeypatch):
  # the rotation breaker cannot move a shard onto an osd which is in the pg, so
  # a host weighs only what its other osds do: osd 0 is in the pg and heavy,
  # which must not draw the moved shard to host0 and its light osd 1
  weight = dict((o, 1.0) for o in range(18))
  weight[0] = 100.0
  monkeypatch.setattr(cluster, 'WEIGHT', weight)
  moved = []
  for ps in range(1000):
    target = cluster.pick_target('3.%x' % ps, [2, 0], [0, 2], HOST)
    moved += [o for o in target if o not in (0, 2)]
  assert moved.count(1) < 100                 # 1/15 of them


def test_target_survives_an_osd_listed_twice(cluster):
  # not something 'pg ls' should report, but the rotation breaker must not
  # count osd 2 twice against host1 and end up weighing it at nothing
  target = cluster.pick_target('3.0', [0, 4, 2, 2], [4, 0, 6, 8], HOST)
  assert len(set(host_of(o) for o in target)) == 4
  assert cluster.rotations([0, 4, 2, 2], target) == []
