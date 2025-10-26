#!/bin/bash

alias fu="fvm use"
alias fl="fvm list"
alias fuup="fvm upgrade"
alias f="fvm flutter"
alias fd="fvm dart"
alias fpub="fvm flutter pub get"
alias fcl="fvm flutter clean"
alias frun="fvm flutter run"
alias fbuild="fvm flutter build"
alias ftest="fvm flutter test"
alias fre="fvm releases"

fb() {
	p=${1:-android} # platform: android or ios
	m=${2:-prod}    # mode: prod (release) or debug
	ts=$(date +%Y_%m_%d_%H_%M)
	v=$(grep "^version:" pubspec.yaml | cut -d" " -f2 | tr "+." "_")
	flag=""
	[[ $m == prod ]] && flag="--release"

	case $p in
	android)
		fvm flutter build apk $flag -t lib/main.dart &&
			cp -i build/app/outputs/flutter-apk/app-${m}.apk flutter_${ts}_v_${v}_${m}.apk
		;;
	ios)
		fvm flutter build ios $flag -t lib/main.dart &&
			cp -i build/ios/ipa/*.ipa flutter_${ts}_v_${v}_${m}.ipa
		;;
	*)
		echo "Unsupported platform: $p"
		return 1
		;;
	esac
}
