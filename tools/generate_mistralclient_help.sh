if [ -z "$1" ];
then
  echo
  echo "Usage: $(basename $0) <output-file>"
  echo
  exit
fi

cmd_list=$(mistral --help | sed -e '1,/Commands for API/d' | cut -d " " -f 3 | grep -vwE "(help|complete|bash-completion)")

file=$1
> $file

for cmd in $cmd_list
do
  echo "Processing help for command $cmd..."
  echo "**$cmd**:" >> $file
  read -d '' helpstr << EOF
  $(mistral help $cmd | sed -e '/output formatters/,$d' | grep -vwE "(--help)")
EOF
  usage=$(echo "$helpstr" | sed -e '/^$/,$d' | sed 's/^/    /')
  helpstr=$(echo "$helpstr" | sed -e '1,/^$/d')
  echo -e "::\n" >> $file
  echo "$usage" >> $file
  echo >> $file
  echo "$helpstr" >> $file
  echo >> $file
done


# Delete empty 'optional arguments:'.
sed -i '/optional arguments:/ {
N
/^optional arguments:\n$/d
}' $file

# Delete extra empty lines.
sed -i '/^$/ {
N
/^\n$/d
}' $file

