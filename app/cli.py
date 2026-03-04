import argparse


def parse_arguments():
    parser = argparse.ArgumentParser(description="IMPulse - Incident Management Platform")
    parser.add_argument(
        '--check',
        action='store_true',
        help='Validate configuration and exit'
    )
    return parser.parse_args()
