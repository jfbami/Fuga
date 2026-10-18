"""Syntax QA only. This is not a Swift compiler, Apple SDK build or on-device test."""
import sys,json,plistlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/swift_parse_packages'))
import tree_sitter_swift
from tree_sitter import Language,Parser
parser=Parser(Language(tree_sitter_swift.language()))
repo=ROOT/'work/github_Fuga'
files=list((repo/'Fuga/Localization').glob('*.swift'))+[repo/'Fuga/ContentView.swift',repo/'Fuga/Navigation/RouteNavigator.swift']
errors=[]
for path in files:
    source=path.read_bytes();tree=parser.parse(source)
    def visit(node):
        if node.type=='ERROR' or node.is_missing:
            errors.append(dict(file=path.name,type=node.type,point=node.start_point,source=source[node.start_byte:node.end_byte].decode(errors='replace')[:160]))
        for child in node.children:visit(child)
    visit(tree.root_node)
plist=plistlib.loads((repo/'Config/Info.plist').read_bytes())
assert plist['NSAppTransportSecurity']['NSAllowsLocalNetworking'] is True
assert 'NSAllowsArbitraryLoads' not in plist['NSAppTransportSecurity']
assert set(plist['NSAppTransportSecurity']['NSExceptionDomains'])=={'192.168.0.0/16','10.0.0.0/8','172.16.0.0/12'}
assert all(k in plist for k in ['NSMicrophoneUsageDescription','NSSpeechRecognitionUsageDescription','NSLocalNetworkUsageDescription'])
assert (repo/'Fuga.xcodeproj/project.pbxproj').read_text().count('INFOPLIST_FILE = Config/Info.plist;')==2
print(json.dumps(dict(swift_files_parsed=len(files),syntax_errors=errors,plist_valid=True,native_ios_build_run=False),indent=2))
sys.exit(bool(errors))
