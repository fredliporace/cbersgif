"""Utilities for searching satellite imagery"""

import json
import re
import requests

from shapely.geometry import mapping

class Search: # pylint: disable=too-few-public-methods
    """General search engine"""

    def __init__(self, search_url):
        """Constructor"""

        self.search_url = search_url

    def is_online(self):
        """True if search service is online"""
        try:
            req = requests.get(self.search_url)
        except: # pylint: disable=W0702
            return False
        return req.ok

class StacSearch(Search):
    """Stac search utilities"""

    def search(self, instrument: str,
               start_date: str, end_date: str,
               bbox: list,
               level: str = None,
               limit: int = 10):
        """
        Search AWS CBERS archive through STAC
        """

        assert instrument in ("MUX", "AWFI", "PAN5M", "PAN10M"), \
            "{} is not a valid instrument".format(instrument)

        #json_geometry = json.dumps(mapping(geometry))
        params = {
            "limit": limit,
            "bbox": bbox,
            "time": "{sd}T00:00:00Z/"\
            "{ed}T12:31:12Z".format(sd=start_date, ed=end_date),
            "query": {
                "eo:instrument":{
                    "eq":instrument
                }
            }
        }

        if level:
            params['query']['cbers:data_type'] = {"eq":level}
        # params['query'].update({} if level is None \
        #                        else {"cbers:data_type":level})

        req = requests.post(self.search_url,
                            json=params,
                            headers={'Content-Type': 'application/json'})

        if req.status_code is not requests.codes.ok: # pylint: disable=no-member
            raise RuntimeError("Service returned %d code, msg: %s" %
                               (req.status_code, req.text))

        res = []
        #import pdb; pdb.set_trace()
        for item in req.json()['features']:
            res.append(item)

        assert len(res) < limit, \
            "Possible truncation on the number of returned scenes"

        return res
