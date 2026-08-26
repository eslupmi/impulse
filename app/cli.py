import argparse


def parse_arguments():
    parser = argparse.ArgumentParser(description="IMPulse - Incident Management Platform")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--check',
        action='store_true',
        help='Validate configuration and exit'
    )
    group.add_argument(
        '--downgrade',
        nargs='?',
        const='',
        default=None,
        metavar='VERSION',
        help='Downgrade incident files one schema step, or to VERSION, and exit',
    )
    return parser.parse_args()
