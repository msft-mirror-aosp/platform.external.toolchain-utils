get_gcc_configure_options()
{
  local CTARGET=$1; shift
  local confgcc=$(get_gcc_common_options)
	case ${CTARGET} in
		arm*)	#264534
			local arm_arch="${CTARGET%%-*}"
			# Only do this if arm_arch is armv*
			if [[ ${arm_arch} == armv* ]] ; then
				# Convert armv7{a,r,m} to armv7-{a,r,m}
				[[ ${arm_arch} == armv7? ]] && arm_arch=${arm_arch/7/7-}
				# Remove endian ('l' / 'eb')
				[[ ${arm_arch} == *l  ]] && arm_arch=${arm_arch%l}
				[[ ${arm_arch} == *eb ]] && arm_arch=${arm_arch%eb}
				confgcc="${confgcc} --with-arch=${arm_arch}"
			fi
			;;
		i?86*)
			confgcc="${confgcc} --with-arch=atom"
			;;
	esac
  echo ${confgcc}
}

get_gcc_common_options()
{
  local confgcc
  # TODO(asharif): Build without these options.
  confgcc="${confgcc} --disable-libmudflap"
  confgcc="${confgcc} --disable-libssp"
  confgcc="${confgcc} --disable-libgomp"
  # Hardened option.
  confgcc="${confgcc} --enable-esp"
  echo ${confgcc}
}

