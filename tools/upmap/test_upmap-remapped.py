# Use importlib since we can't import a module that contains a hyphen
import importlib
upmap_remapped = importlib.import_module('upmap-remapped')

def test_gen_upmap(monkeypatch):
  OSDS = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
  DF = [
    {"id": 0, "crush_weight": 14, "reweight": 1},
    {"id": 1, "crush_weight": 8, "reweight": 1},
    {"id": 2, "crush_weight": 12, "reweight": 1},
    {"id": 3, "crush_weight": 8, "reweight": 1},
    {"id": 4, "crush_weight": 12, "reweight": 1},
    {"id": 5, "crush_weight": 10, "reweight": 1},
    {"id": 6, "crush_weight": 12, "reweight": 1},
    {"id": 7, "crush_weight": 8, "reweight": 1},
    {"id": 8, "crush_weight": 12, "reweight": 1},
    {"id": 9, "crush_weight": 8, "reweight": 1},
    {"id": 10, "crush_weight": 10, "reweight": 1},
    {"id": 11, "crush_weight": 10, "reweight": 1},
    {"id": 12, "crush_weight": 10, "reweight": 1},
    {"id": 13, "crush_weight": 10, "reweight": 1},
    {"id": 14, "crush_weight": 10, "reweight": 1},
    {"id": 15, "crush_weight": 10, "reweight": 1}
  ]

  # Use monkeypatch to set the required globals
  monkeypatch.setattr(upmap_remapped, "OSDS", OSDS)
  monkeypatch.setattr(upmap_remapped, "DF", DF)

  # EC 4+2 - single
  assert upmap_remapped.gen_upmap([2,11,5,9,15,12], [2,11,5,9,14,12]) == [(15,14)]

  # EC 4+2 - every osd remapped with no dependencies
  assert upmap_remapped.gen_upmap([4,14,10,3,7,8], [9,13,2,15,5,11]) == [(4,9),(14,13),(10,2),(3,15),(7,5),(8,11)]

  # EC 4+2 - one dependency
  assert upmap_remapped.gen_upmap([6,12,10,0,2,9], [6,12,9,0,2,4]) == [(9,4),(10,9)]

  # EC 4+2 - two dependencies
  assert upmap_remapped.gen_upmap([3,4,12,6,11,0], [6,14,12,4,11,0]) == [(4,14),(6,4),(3,6)]

  # EC 4+2 - three dependencies plus one without a dependency
  assert upmap_remapped.gen_upmap([7,1,12,2,15,9], [7,0,4,12,9,2]) == [(1,0),(12,4),(2,12),(9,2),(15,9)]

  # EC 4+2 - upmap not possible since osds are swapped
  assert upmap_remapped.gen_upmap([9,4,7,10,14,2], [9,7,4,10,14,2]) == []
