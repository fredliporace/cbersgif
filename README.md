# cbersgif

Animated GIFs from CBERS data on AWS.

WIP project, check [landsatgif](https://github.com/vincentsarago/landsatgif) and [sentinelgif](https://github.com/fredliporace/sentinelgif) for related projects.

## Example

Usage example:

```
./cbersgif/cli.py --lat -12.8379 --lon -56.01551 --path 167 --row 114 --sensor MUX --max_images 50 --enhancement --buffer_size=20000 --res=80 --duration=0.5 --taboo_index=3,4,5,6,9,11,20,22,26
```

Results in:

![](img_samples/1426060a-f0a8-11e8-b241-080027243b40.gif)

## Installation

Tested with python 3.6.5

```
pip install -r requirements.txt
```

### AWS

AWS access credentials must be available. Note that charges apply to data access.

Requires setting the AWS_REQUESTER_PAYER env var to be set:

```
AWS_REQUEST_PAYER="requester"
```
