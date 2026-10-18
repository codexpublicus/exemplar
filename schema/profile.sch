<?xml version="1.0" encoding="UTF-8"?>
<!--
  Schematron rules for spec/akoma-ntoso-profile.md 0.1.x.

  These rules check what the Akoma Ntoso 1.0 XML Schema can't: the profile's rules marked
  "Schematron" in section 16.2 of the profile. Run them after XSD validation; a document that
  fails the XSD can make these rules report misleading errors.

  Every assertion message starts with the rule id it enforces, [AKN-n], or with the section
  number, [5.1.2], for a requirement the profile states without a rule id.

  Query binding xslt2 (XPath 2.0). The reference runner is validator/validate.py (Saxon HE with
  the vendored SchXslt2 transpiler); any ISO Schematron processor with XSLT 2.0 or later should
  give the same results.

  Open questions O2 (the form of key URIs) and O7 (decisions without a decision key) are to be
  settled with codexpublicus/exemplar#4. These rules implement the 0.1.0 text, which takes
  option (a) for both: FRBR URIs and ref targets are bare keys, and every document has one.
  They don't check anything those questions leave open. Registry hrefs are checked only for
  their fragment and their agreement with cx:registry/@uri, not for the form of the URI, and
  every check that reads a key from a URI goes through f:key-of-uri, the one function O2
  would change.
-->
<schema xmlns="http://purl.oclc.org/dsdl/schematron"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:xs="http://www.w3.org/2001/XMLSchema"
        xmlns:f="https://codexpublicus.org/ns/exemplar/functions"
        queryBinding="xslt2">

  <title>Akoma Ntoso judgment profile for US decisions, 0.1.x</title>

  <ns prefix="a" uri="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"/>
  <ns prefix="cx" uri="https://codexpublicus.org/ns/exemplar"/>
  <ns prefix="f" uri="https://codexpublicus.org/ns/exemplar/functions"/>
  <ns prefix="xs" uri="http://www.w3.org/2001/XMLSchema"/>

  <!-- The court record key regex, byte-identical to spec/court-record-key.md section 2.2. -->
  <xsl:function name="f:crk-regex" as="xs:string">
    <xsl:sequence select="'^us/([a-z][a-z0-9-]*)/([a-z0-9][a-z0-9_.-]*)/([0-9]{4}-[0-9]{2}-[0-9]{2})(~([2-9]|[1-9][0-9]+))?(/(opinion|per-curiam|plurality|concurrence|concurrence-in-judgment|concurrence-in-part-and-judgment|partial|partial-majority|dissent|statement|order|judgment|decree)(\.[a-z][a-z-]*(\+[a-z][a-z-]*)*)?(~([2-9]|[1-9][0-9]+))?)?(@[0-9]{4}-[0-9]{2}-[0-9]{2})?$'"/>
  </xsl:function>

  <!-- Alias schemes, CRK spec section 11.1: scheme name and the regex for the whole alias. -->
  <xsl:function name="f:alias-schemes" as="xs:string+">
    <xsl:sequence select="('cite', 'neutral', 'scotus-r', 'ca6', 'cmecf', 'govinfo', 'cap', 'cl-cluster', 'cl-opinion')"/>
  </xsl:function>
  <xsl:function name="f:alias-regexes" as="xs:string+">
    <xsl:sequence select="(
      '^cite:[0-9]+-[a-z0-9][a-z0-9-]*-[0-9]+$',
      '^neutral:[a-z0-9][a-z0-9-]*$',
      '^scotus-r:[0-9]{4}-[0-9]+$',
      '^ca6:[0-9]{2}a[0-9]{4}[pn]\.06$',
      '^cmecf:[a-z][a-z0-9-]*:[0-9]+$',
      '^govinfo:[A-Za-z0-9_-]+$',
      '^cap:[a-z0-9][a-z0-9-]*/[0-9]+/[0-9]+-[0-9]{2}$',
      '^cl-cluster:[1-9][0-9]*$',
      '^cl-opinion:[1-9][0-9]*$')"/>
  </xsl:function>

  <!-- O2: the key a URI value names. Under 0.1.0 (option a) the value is the bare key. -->
  <xsl:function name="f:key-of-uri" as="xs:string">
    <xsl:param name="uri" as="xs:string?"/>
    <xsl:sequence select="string($uri)"/>
  </xsl:function>

  <xsl:function name="f:is-date" as="xs:boolean">
    <xsl:param name="s" as="xs:string?"/>
    <xsl:sequence select="matches(string($s), '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') and string($s) castable as xs:date"/>
  </xsl:function>

  <!-- The parts of a key. They assume nothing about the input and return empty strings for
       strings that aren't keys; f:is-key decides validity. -->
  <xsl:function name="f:body" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="if (contains(string($key), '@')) then substring-before($key, '@') else string($key)"/>
  </xsl:function>
  <xsl:function name="f:revised" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="substring-after(string($key), '@')"/>
  </xsl:function>
  <xsl:function name="f:segment" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:param name="n" as="xs:integer"/>
    <xsl:sequence select="string(tokenize(f:body($key), '/')[$n])"/>
  </xsl:function>
  <xsl:function name="f:court" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="f:segment($key, 2)"/>
  </xsl:function>
  <xsl:function name="f:docket" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="f:segment($key, 3)"/>
  </xsl:function>
  <xsl:function name="f:decided" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="replace(f:segment($key, 4), '~.*$', '')"/>
  </xsl:function>
  <xsl:function name="f:decision-ordinal" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="substring-after(f:segment($key, 4), '~')"/>
  </xsl:function>
  <xsl:function name="f:decision-key" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="string-join(tokenize(f:body($key), '/')[position() le 4], '/')"/>
  </xsl:function>
  <!-- The part segment, {role}[.{authors}][~n], or '' for a decision or version key. -->
  <xsl:function name="f:part" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="f:segment($key, 5)"/>
  </xsl:function>
  <xsl:function name="f:role" as="xs:string">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:sequence select="replace(f:part($key), '[.~].*$', '')"/>
  </xsl:function>
  <xsl:function name="f:authors" as="xs:string*">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:variable name="head" select="replace(f:part($key), '~.*$', '')"/>
    <xsl:sequence select="if (contains($head, '.')) then tokenize(substring-after($head, '.'), '\+') else ()"/>
  </xsl:function>

  <!-- A valid key: CRK spec sections 2.2 and 2.3. -->
  <xsl:function name="f:is-key" as="xs:boolean">
    <xsl:param name="key" as="xs:string?"/>
    <xsl:variable name="s" select="string($key)"/>
    <xsl:sequence select="matches($s, f:crk-regex())
        and f:is-date(f:decided($s))
        and (f:revised($s) eq '' or (f:is-date(f:revised($s)) and f:revised($s) ge f:decided($s)))
        and (not(starts-with(f:docket($s), 'rpt.')) or matches(f:docket($s), '^rpt\.[0-9]+-[a-z0-9][a-z0-9-]*-[0-9]+$'))
        and not(f:role($s) eq 'per-curiam' and exists(f:authors($s)))"/>
  </xsl:function>

  <!-- The alias scheme of a {scheme}:{value} alias, or '' when the string is not one. -->
  <xsl:function name="f:alias-scheme" as="xs:string">
    <xsl:param name="alias" as="xs:string?"/>
    <xsl:variable name="s" select="string($alias)"/>
    <xsl:sequence select="string((for $i in 1 to count(f:alias-schemes())
        return if (matches($s, f:alias-regexes()[$i])) then f:alias-schemes()[$i] else ())[1])"/>
  </xsl:function>

  <!-- A reporter abbreviation reduced to a slug, CRK spec section 5.6. -->
  <xsl:function name="f:slug" as="xs:string">
    <xsl:param name="text" as="xs:string?"/>
    <xsl:sequence select="replace(normalize-space(replace(lower-case(string($text)), &quot;[.'’(),]&quot;, '')), ' ', '-')"/>
  </xsl:function>

  <!-- The element whose eId prefixes a paragraph's eId (sections 6, 8.1, 11.1). -->
  <xsl:function name="f:container" as="element()?">
    <xsl:param name="e" as="element()"/>
    <xsl:sequence select="$e/ancestor::*[self::a:hcontainer or self::a:authorialNote or self::a:blockContainer or self::a:note][1]"/>
  </xsl:function>

  <!-- The trailing number of an eId ending _{n}, or -1. -->
  <xsl:function name="f:eid-number" as="xs:integer">
    <xsl:param name="eid" as="xs:string?"/>
    <xsl:variable name="n" select="replace(string($eid), '^.*_', '')"/>
    <xsl:sequence select="if (matches($n, '^[1-9][0-9]*$')) then xs:integer($n) else -1"/>
  </xsl:function>

  <let name="profile-line" value="'0.1'"/>
  <let name="meta" value="/a:akomaNtoso/a:judgment/a:meta"/>
  <let name="work" value="f:key-of-uri($meta/a:identification/a:FRBRWork/a:FRBRthis/@value)"/>
  <let name="expression" value="f:key-of-uri($meta/a:identification/a:FRBRExpression/a:FRBRthis/@value)"/>
  <let name="producer" value="string($meta/a:identification/a:FRBRManifestation/a:FRBRauthor/@href)"/>
  <let name="court-ref" value="concat('#court_', f:court($work))"/>
  <let name="references" value="$meta/a:references"/>
  <let name="proprietary" value="$meta/a:proprietary"/>
  <let name="courts-uri" value="string(($proprietary/cx:keys/cx:registry[@name = 'courts'])[1]/@uri)"/>
  <let name="judges-uri" value="string(($proprietary/cx:keys/cx:registry[@name = 'judges'])[1]/@uri)"/>
  <let name="decision-roles" value="('order', 'judgment', 'decree')"/>

  <!-- Section 4: document outline. -->
  <pattern id="outline">
    <rule context="/a:akomaNtoso">
      <assert test="a:judgment and count(*) eq 1">[AKN-4] The root holds exactly one judgment and no components.</assert>
    </rule>
    <rule context="/a:akomaNtoso/a:judgment">
      <assert test="@name eq 'judgment'">[AKN-5] judgment/@name is "judgment", not "<value-of select="@name"/>".</assert>
      <assert test="@contains eq (if (f:revised($expression) ne '') then 'singleVersion' else 'originalVersion')">[AKN-6] judgment/@contains is "<value-of select="if (f:revised($expression) ne '') then 'singleVersion' else 'originalVersion'"/>" for expression "<value-of select="$expression"/>", not "<value-of select="@contains"/>".</assert>
      <assert test="not(.//a:coverPage or .//a:conclusions or .//a:attachments or .//a:components)">[AKN-7] coverPage, conclusions, attachments and components are not used.</assert>
    </rule>
    <rule context="a:judgmentBody">
      <assert test="not(a:background or a:arguments or a:remedies)">[AKN-38] background, arguments and remedies are not used.</assert>
    </rule>
    <rule context="a:judgmentBody/a:motivation | a:judgmentBody/a:decision">
      <assert test="every $c in * satisfies $c/self::a:hcontainer">[AKN-39] <value-of select="local-name()"/> holds only part hcontainers.</assert>
    </rule>
  </pattern>

  <!-- Section 5.1: identification. -->
  <pattern id="identification">
    <rule context="a:meta/a:identification">
      <assert test="@source eq $producer">[AKN-8] identification/@source references the producer, "<value-of select="$producer"/>".</assert>
    </rule>
    <rule context="a:identification/a:FRBRWork">
      <let name="this" value="f:key-of-uri(a:FRBRthis/@value)"/>
      <assert test="f:is-key($this) and f:part($this) eq '' and f:revised($this) eq ''">[AKN-9] The work URI "<value-of select="$this"/>" is a valid decision key.</assert>
      <assert test="every $u in a:FRBRuri satisfies f:key-of-uri($u/@value) eq $this">[AKN-9] FRBRWork/FRBRuri equals FRBRthis.</assert>
      <assert test="a:FRBRdate and (every $d in a:FRBRdate satisfies ($d/@name eq 'decided' and string($d/@date) eq f:decided($this)))">[AKN-11] FRBRWork/FRBRdate is the decision date, <value-of select="f:decided($this)"/>, named "decided".</assert>
      <assert test="every $a in a:FRBRauthor satisfies $a/@href eq $court-ref">[AKN-12] FRBRWork/FRBRauthor/@href is "<value-of select="$court-ref"/>".</assert>
      <assert test="a:FRBRcountry/@value eq 'us'">[AKN-13] FRBRcountry/@value is "us".</assert>
      <assert test="every $n in a:FRBRnumber satisfies $n/@value eq f:docket($this)">[5.1.1] FRBRnumber/@value is the key's docket segment, "<value-of select="f:docket($this)"/>".</assert>
    </rule>
    <rule context="a:identification/a:FRBRWork/a:FRBRalias">
      <let name="key" value="f:key-of-uri(../a:FRBRthis/@value)"/>
      <let name="akn-nc" value="concat('/akn/us/judgment/', f:court($key), '/', f:decided($key), '/', f:docket($key))"/>
      <assert test="if (@name eq 'akn-nc') then (f:decision-ordinal($key) ne '' or @value eq $akn-nc)
                    else if (@name eq 'vendor') then normalize-space(@value) ne ''
                    else if (@name = f:alias-schemes()) then (@name ne 'cl-opinion' and f:alias-scheme(@value) eq @name)
                    else (f:is-key(@value) and f:part(@value) eq '' and f:revised(@value) eq '')">[AKN-10] FRBRalias name="<value-of select="@name"/>" value="<value-of select="@value"/>" is an alias of the decision under that scheme (CRK section 11.1), "akn-nc", "vendor", or a key-shaped alias.</assert>
    </rule>
    <rule context="a:identification/a:FRBRExpression">
      <let name="this" value="f:key-of-uri(a:FRBRthis/@value)"/>
      <let name="date-name" value="if (f:revised($this) ne '') then 'revised' else 'decided'"/>
      <let name="date" value="if (f:revised($this) ne '') then f:revised($this) else f:decided($this)"/>
      <assert test="f:is-key($this) and f:part($this) eq '' and f:decision-key($this) eq $work">[AKN-15] The expression URI "<value-of select="$this"/>" is a valid version key of the work "<value-of select="$work"/>".</assert>
      <assert test="every $u in a:FRBRuri satisfies f:key-of-uri($u/@value) eq $this">[AKN-15] FRBRExpression/FRBRuri equals FRBRthis.</assert>
      <assert test="a:FRBRdate and (every $d in a:FRBRdate satisfies ($d/@name eq $date-name and string($d/@date) eq $date))">[AKN-16] FRBRExpression/FRBRdate is named "<value-of select="$date-name"/>" with date <value-of select="$date"/>.</assert>
      <assert test="every $a in a:FRBRauthor satisfies $a/@href eq $court-ref">[5.1.2] FRBRExpression/FRBRauthor/@href is "<value-of select="$court-ref"/>", as in FRBRWork.</assert>
      <assert test="a:FRBRauthoritative/@value eq 'false'">[AKN-17] FRBRauthoritative/@value is "false".</assert>
    </rule>
    <rule context="a:identification/a:FRBRManifestation">
      <let name="this" value="concat($expression, '.akn.xml')"/>
      <assert test="a:FRBRthis/@value eq $this and (every $u in a:FRBRuri satisfies $u/@value eq $this)">[AKN-18] The manifestation URI is "<value-of select="$this"/>".</assert>
      <assert test="matches(string(a:FRBRauthor/@href), '^#org_') and $references/a:TLCOrganization[concat('#', @eId) eq current()/a:FRBRauthor/@href]">[AKN-19] FRBRManifestation/FRBRauthor/@href references the producer's TLCOrganization (an org_ eId).</assert>
      <assert test="a:FRBRformat/@value eq 'application/akn+xml'">[AKN-20] FRBRformat/@value is "application/akn+xml".</assert>
      <assert test="a:FRBRdate/@name = 'generated'">[5.1.3] FRBRManifestation/FRBRdate is named "generated".</assert>
    </rule>
  </pattern>

  <!-- Section 5.2: references. -->
  <pattern id="references">
    <rule context="a:meta/a:references">
      <assert test="@source eq $producer">[AKN-21] references/@source references the producer, "<value-of select="$producer"/>".</assert>
      <assert test="count(a:TLCOrganization[starts-with(@eId, 'court_')]) eq 1">[AKN-22] references lists exactly one court.</assert>
    </rule>
    <rule context="a:references/a:TLCOrganization[starts-with(@eId, 'court_')]">
      <let name="code" value="f:court($work)"/>
      <assert test="@eId eq concat('court_', $code)">[AKN-22] The court's eId is "court_<value-of select="$code"/>", the key's court code.</assert>
      <assert test="if ($courts-uri ne '') then @href eq concat($courts-uri, '#', $code) else ends-with(@href, concat('#', $code))">[AKN-22] The court's href is the court registry entry, "<value-of select="$courts-uri"/>#<value-of select="$code"/>".</assert>
    </rule>
    <rule context="a:references/a:TLCOrganization">
      <assert test="matches(@eId, '^org_\S+$')">[AKN-22] An organization other than the court has an eId "org_{name}", not "<value-of select="@eId"/>".</assert>
    </rule>
    <rule context="a:references/a:TLCPerson">
      <assert test="matches(@eId, '^[a-z][a-z-]*$')">[AKN-22] A judge's eId is a judge slug, not "<value-of select="@eId"/>".</assert>
      <assert test="if ($judges-uri ne '') then @href eq concat($judges-uri, '#', @eId) else ends-with(@href, concat('#', @eId))">[AKN-22] A judge's href is the judge registry entry, "<value-of select="$judges-uri"/>#<value-of select="@eId"/>".</assert>
    </rule>
    <rule context="a:references/a:TLCReference[@name = 'printing']">
      <assert test="matches(@eId, '^printing_[0-9]+-[a-z0-9][a-z0-9-]*-[0-9]+$')">[AKN-22] A printing's eId is "printing_{volume}-{reporter slug}-{page}", not "<value-of select="@eId"/>".</assert>
      <assert test="@href eq concat('cite:', substring-after(@eId, 'printing_'))">[AKN-22] A printing's href is its cite: alias, "cite:<value-of select="substring-after(@eId, 'printing_')"/>".</assert>
      <assert test="count($proprietary/cx:printing[@ref eq concat('#', current()/@eId)]) eq 1">[AKN-24] Printing "<value-of select="@eId"/>" has exactly one cx:printing.</assert>
    </rule>
    <rule context="a:references/a:TLCReference[@name = 'source']">
      <assert test="matches(@eId, '^source_\S+$')">[AKN-22] A source's eId is "source_{name}", not "<value-of select="@eId"/>".</assert>
      <assert test="f:alias-scheme(@href) ne ''">[AKN-22] A source's href is an alias of its record, not "<value-of select="@href"/>".</assert>
      <assert test="count($proprietary/cx:source[@ref eq concat('#', current()/@eId)]) eq 1">[AKN-25] Source "<value-of select="@eId"/>" has exactly one cx:source.</assert>
    </rule>
  </pattern>

  <!-- Sections 2 and 5.3: proprietary metadata. -->
  <pattern id="proprietary">
    <rule context="a:meta/a:proprietary">
      <assert test="@source eq $producer">[5.3] proprietary/@source references the producer, "<value-of select="$producer"/>".</assert>
      <assert test="count(cx:profile) eq 1">[AKN-2] proprietary holds exactly one cx:profile.</assert>
      <assert test="count(cx:keys) eq 1">[AKN-23] proprietary holds exactly one cx:keys.</assert>
    </rule>
    <rule context="cx:profile">
      <assert test="matches(string(@version), concat('^', replace($profile-line, '\.', '\\.'), '\.(0|[1-9][0-9]*)$'))">[AKN-2] cx:profile/@version is a <value-of select="$profile-line"/>.x version, not "<value-of select="@version"/>"; these rules check profile <value-of select="$profile-line"/>.x.</assert>
    </rule>
    <rule context="cx:keys">
      <assert test="@provenance = ('engine-output', 'human-curated')">[AKN-56] cx:keys/@provenance is "engine-output" or "human-curated", not "<value-of select="@provenance"/>".</assert>
      <assert test="count(cx:registry[@name eq 'courts']) eq 1">[AKN-23] cx:keys lists the court registry.</assert>
      <assert test="count(cx:registry[@name eq 'judges']) le 1 and (cx:registry[@name eq 'judges'] or not(//a:hcontainer[@cx:authors]))">[AKN-23] cx:keys lists the judge registry, once, when a part key has authors.</assert>
    </rule>
    <rule context="cx:keys/cx:registry">
      <assert test="@name = ('courts', 'judges') and normalize-space(@uri) ne '' and normalize-space(@version) ne ''">[AKN-23] cx:registry has @name "courts" or "judges", a @uri and a @version.</assert>
    </rule>
    <rule context="cx:printing">
      <let name="ref" value="$references/a:TLCReference[@name = 'printing'][concat('#', @eId) eq current()/@ref]"/>
      <assert test="exists($ref)">[AKN-24] cx:printing/@ref "<value-of select="@ref"/>" references a printing in references.</assert>
      <assert test="@type = ('official', 'parallel')">[AKN-24] cx:printing/@type is "official" or "parallel", not "<value-of select="@type"/>".</assert>
      <assert test="normalize-space(@reporter) ne '' and normalize-space(@volume) ne '' and normalize-space(@firstPage) ne ''">[AKN-24] cx:printing has @reporter, @volume and @firstPage.</assert>
      <assert test="not(exists($ref)) or $ref/@eId eq concat('printing_', @volume, '-', f:slug(@reporter), '-', @firstPage)">[AKN-22] The printing's eId is "printing_<value-of select="concat(@volume, '-', f:slug(@reporter), '-', @firstPage)"/>", from its volume, reporter and first page.</assert>
      <assert test="@text = ('transcribed', 'withheld', 'unavailable')">[AKN-24] cx:printing/@text is "transcribed", "withheld" or "unavailable", not "<value-of select="@text"/>".</assert>
      <assert test="not(@ordinal) or matches(@ordinal, '^[1-9][0-9]*$')">[AKN-24] cx:printing/@ordinal is a positive integer.</assert>
    </rule>
    <rule context="cx:printing/cx:cite">
      <assert test="normalize-space(@type) ne '' and normalize-space(@value) ne ''">[AKN-24] cx:cite has @type and @value.</assert>
    </rule>
    <rule context="cx:printing/cx:scans">
      <assert test="$references/a:TLCReference[@name = 'source'][concat('#', @eId) eq current()/@source]">[AKN-24] cx:scans/@source "<value-of select="@source"/>" references a source in references.</assert>
      <assert test="normalize-space(@volume) ne '' and matches(@first, '^[1-9][0-9]*$') and matches(@last, '^[1-9][0-9]*$') and xs:integer(@first) le xs:integer(@last)">[AKN-24] cx:scans has @volume, and @first and @last are scan sequence numbers with @first not after @last.</assert>
    </rule>
    <rule context="cx:source">
      <let name="ref" value="$references/a:TLCReference[@name = 'source'][concat('#', @eId) eq current()/@ref]"/>
      <assert test="exists($ref)">[AKN-25] cx:source/@ref "<value-of select="@ref"/>" references a source in references.</assert>
      <assert test="not(exists($ref)) or @record eq $ref/@href">[AKN-25] cx:source/@record is the source's alias, "<value-of select="$ref/@href"/>".</assert>
      <assert test="$references/a:TLCOrganization[starts-with(@eId, 'org_')][concat('#', @eId) eq current()/@agent]">[AKN-25] cx:source/@agent "<value-of select="@agent"/>" references an organization in references.</assert>
      <assert test="@method = ('ocr', 'born-digital', 'keyed', 'unknown')">[AKN-25] cx:source/@method is "ocr", "born-digital", "keyed" or "unknown", not "<value-of select="@method"/>".</assert>
    </rule>
    <rule context="cx:source/cx:confidence">
      <assert test="@value castable as xs:decimal and normalize-space(@scope) ne '' and normalize-space(@basis) ne ''">[5.3] cx:confidence has a numeric @value, a @scope and a @basis.</assert>
    </rule>
  </pattern>

  <!-- Section 6: header. -->
  <pattern id="header">
    <rule context="a:judgment/a:header/*">
      <let name="kind" value="local-name()"/>
      <let name="prev" value="preceding-sibling::*[local-name() eq $kind][1]"/>
      <assert test="self::a:p or self::a:blockContainer">[AKN-26] A header block is a p or a blockContainer, not <value-of select="$kind"/>.</assert>
      <assert test="@class = ('parties', 'docketnumber', 'court', 'decisiondate', 'otherdate', 'attorneys', 'judges', 'syllabus', 'headnotes', 'summary', 'synopsis', 'history', 'disposition', 'posture', 'arguments', 'statement', 'headmatter')">[AKN-26] Header block @class "<value-of select="@class"/>" is in the vocabulary of section 6.</assert>
      <assert test="@cx:origin">[AKN-26] A header block has @cx:origin.</assert>
      <assert test="matches(string(@eId), concat('^header__', $kind, '_[1-9][0-9]*$')) and (not($prev) or f:eid-number($prev/@eId) lt f:eid-number(@eId))">[AKN-26] Header block eId "<value-of select="@eId"/>" is "header__<value-of select="$kind"/>_{n}", numbered in order.</assert>
      <assert test="not(@class = ('syllabus', 'headnotes', 'summary', 'synopsis') and @cx:origin eq 'court')">[AKN-27] A header block of class "<value-of select="@class"/>" doesn't have @cx:origin "court".</assert>
    </rule>
  </pattern>

  <!-- Section 7: parts. -->
  <pattern id="parts">
    <rule context="a:judgmentBody/a:motivation/a:hcontainer | a:judgmentBody/a:decision/a:hcontainer">
      <let name="key" value="string(@cx:part)"/>
      <let name="role" value="f:role($key)"/>
      <let name="authors" value="f:authors($key)"/>
      <let name="expected-type" value="if ($role = ('concurrence', 'concurrence-in-judgment', 'concurrence-in-part-and-judgment')) then 'agreeing' else if ($role eq 'dissent') then 'dissenting' else ''"/>
      <let name="opinion" value="a:heading/a:opinion"/>
      <assert test="f:is-key($key) and f:part($key) ne '' and f:decision-key($key) eq $work and (f:revised($key) eq '' or f:revised($key) eq f:revised($expression))">[AKN-31] @cx:part "<value-of select="$key"/>" is a valid part key of the work "<value-of select="$work"/>".</assert>
      <assert test="count(//a:hcontainer[@cx:part eq $key]) eq 1">[AKN-31] Part key "<value-of select="$key"/>" names one part.</assert>
      <assert test="@name eq $role">[AKN-29] The part's @name is its role, "<value-of select="$role"/>".</assert>
      <assert test="@eId eq concat('opinion_', f:part($key))">[AKN-30] The part's eId is "opinion_<value-of select="f:part($key)"/>".</assert>
      <assert test="if (exists($authors)) then @cx:authors eq string-join($authors, ' ') else not(@cx:authors)">[AKN-32] @cx:authors lists the part key's authors, "<value-of select="string-join($authors, ' ')"/>", and is absent when it has none.</assert>
      <assert test="every $s in $authors satisfies $references/a:TLCPerson[@eId eq $s]">[AKN-22] Each author of "<value-of select="$key"/>" has a TLCPerson.</assert>
      <assert test="not(@cx:joinedBy) or (matches(@cx:joinedBy, '^[a-z][a-z-]*( [a-z][a-z-]*)*$') and (every $s in tokenize(@cx:joinedBy, ' ') satisfies $references/a:TLCPerson[@eId eq $s]))">[AKN-33] @cx:joinedBy lists judge slugs separated by single spaces, each with a TLCPerson.</assert>
      <assert test="if (not($opinion) and $role = $decision-roles) then true() else count($opinion) eq 1 and $opinion/@by eq (if (exists($authors)) then concat('#', $authors[1]) else $court-ref)">[AKN-34] The heading holds one opinion whose @by is "<value-of select="if (exists($authors)) then concat('#', $authors[1]) else $court-ref"/>".</assert>
      <assert test="every $o in $opinion satisfies (if ($expected-type ne '') then $o/@type eq $expected-type else not($o/@type))">[AKN-35] opinion/@type is <value-of select="if ($expected-type ne '') then concat('&quot;', $expected-type, '&quot;') else 'absent'"/> for role "<value-of select="$role"/>".</assert>
      <assert test="if ($role = $decision-roles) then parent::a:decision else parent::a:motivation">[AKN-36] A part with role "<value-of select="$role"/>" goes in <value-of select="if ($role = $decision-roles) then 'decision' else 'motivation'"/>.</assert>
      <assert test="not(@cx:aliases) or matches(@cx:aliases, '^cl-opinion:[1-9][0-9]*( cl-opinion:[1-9][0-9]*)*$')">[7.2] @cx:aliases lists cl-opinion aliases separated by single spaces.</assert>
    </rule>
  </pattern>

  <!-- Sections 8.1 and 11: paragraph eIds. Producer-inserted paragraphs have none (8.3). -->
  <pattern id="paragraphs">
    <rule context="*[self::a:p or self::a:block][not(@cx:origin eq 'producer')][f:container(.)][@eId or not(f:container(.)/self::a:note)]">
      <let name="c" value="f:container(.)"/>
      <let name="prefix" value="concat($c/@eId, '__p_')"/>
      <let name="prev" value="(preceding::*[self::a:p or self::a:block][@eId][not(@cx:origin eq 'producer')][f:container(.) is $c])[last()]"/>
      <assert test="starts-with(string(@eId), $prefix) and matches(substring(string(@eId), string-length($prefix) + 1), '^[1-9][0-9]*$')">[AKN-40] eId "<value-of select="@eId"/>" is "<value-of select="$prefix"/>{n}".</assert>
      <assert test="not($prev) or f:eid-number($prev/@eId) lt f:eid-number(@eId)">[AKN-40] eId "<value-of select="@eId"/>" follows "<value-of select="$prev/@eId"/>" in increasing order.</assert>
    </rule>
  </pattern>

  <!-- Section 8.2: scan anchors. -->
  <pattern id="blocks">
    <rule context="*[@cx:blocks]">
      <assert test="matches(@cx:blocks, '^[\i-[:]][\c-[:]]*( [\i-[:]][\c-[:]]*)*$')">[AKN-43] @cx:blocks "<value-of select="@cx:blocks"/>" lists block ids separated by single spaces.</assert>
    </rule>
  </pattern>

  <!-- Section 8.3: omissions. -->
  <pattern id="omissions">
    <rule context="a:hcontainer[@cx:part]//a:p[@cx:origin eq 'producer' or (a:omissis and not(text()[normalize-space()]) and (every $c in * satisfies ($c/self::a:omissis or $c/self::a:eop or $c/self::a:eol)))]">
      <assert test="@cx:origin eq 'producer' and not(@eId)">[AKN-44] A paragraph the producer inserts to hold omissions has @cx:origin "producer" and no eId.</assert>
    </rule>
  </pattern>

  <!-- Section 9: page and line markers. -->
  <pattern id="markers">
    <rule context="a:eop">
      <let name="printing" value="$proprietary/cx:printing[@ref eq current()/@refersTo]"/>
      <assert test="$references/a:TLCReference[@name = 'printing'][concat('#', @eId) eq current()/@refersTo]">[AKN-46] eop/@refersTo "<value-of select="@refersTo"/>" references a printing.</assert>
      <assert test="normalize-space(@number) ne ''">[AKN-47] eop has @number.</assert>
      <assert test="not(@number castable as xs:integer and $printing/@firstPage castable as xs:integer)
                    or (xs:integer(@number) gt xs:integer($printing/@firstPage)
                        and (not($printing/@lastPage castable as xs:integer) or xs:integer(@number) le xs:integer($printing/@lastPage)))">[AKN-47] eop/@number <value-of select="@number"/> is a page of printing "<value-of select="@refersTo"/>" after its first page, <value-of select="$printing/@firstPage"/>, and not after its last.</assert>
      <assert test="not(@cx:scan) or (matches(@cx:scan, '^[1-9][0-9]*$') and (not($printing/cx:scans) or (some $s in $printing/cx:scans satisfies (xs:integer(@cx:scan) ge xs:integer($s/@first) and xs:integer(@cx:scan) le xs:integer($s/@last)))))">[9.1] eop/@cx:scan "<value-of select="@cx:scan"/>" is a scan sequence number within the printing's cx:scans.</assert>
    </rule>
    <rule context="a:eol">
      <assert test="$references/a:TLCReference[@name = 'printing'][concat('#', @eId) eq current()/@refersTo]">[AKN-49] eol/@refersTo "<value-of select="@refersTo"/>" references a printing.</assert>
    </rule>
  </pattern>

  <!-- Section 10: citations. -->
  <pattern id="citations">
    <rule context="a:ref">
      <let name="target" value="f:key-of-uri(@href)"/>
      <assert test="normalize-space(.) ne ''">[AKN-50] A ref's text is the citation as printed.</assert>
      <assert test="f:is-key($target) or f:alias-scheme(@href) ne ''">[AKN-51] ref/@href "<value-of select="@href"/>" is a key or an alias of a decision.</assert>
    </rule>
  </pattern>

  <!-- Section 11: footnotes and notes. -->
  <pattern id="notes">
    <rule context="a:authorialNote">
      <let name="part" value="ancestor::a:hcontainer[@cx:part][1]"/>
      <let name="prefix" value="concat($part/@eId, '__authorialNote_')"/>
      <let name="prev" value="(preceding::a:authorialNote[ancestor::a:hcontainer[@cx:part][1] is $part])[last()]"/>
      <assert test="exists($part)">[AKN-54] An authorialNote is in a part; a footnote in the head matter is a note (section 11.2).</assert>
      <assert test="normalize-space(@marker) ne '' and @placement eq 'bottom'">[AKN-54] An authorialNote has @marker and @placement "bottom".</assert>
      <assert test="starts-with(string(@eId), $prefix) and matches(substring(string(@eId), string-length($prefix) + 1), '^[1-9][0-9]*$') and (not($prev) or f:eid-number($prev/@eId) lt f:eid-number(@eId))">[AKN-54] authorialNote eId "<value-of select="@eId"/>" is "<value-of select="$prefix"/>{n}", numbered in order.</assert>
    </rule>
    <rule context="a:meta/a:notes/a:note">
      <assert test="matches(string(@eId), '^note_[1-9][0-9]*$') and normalize-space(@marker) ne '' and @cx:origin">[AKN-55] A head matter note has eId "note_{n}", @marker and @cx:origin.</assert>
      <assert test="//a:noteRef[@href eq concat('#', current()/@eId)]">[AKN-55] Note "<value-of select="@eId"/>" has a noteRef at its reference mark.</assert>
    </rule>
    <rule context="a:noteRef">
      <assert test="$meta/a:notes/a:note[concat('#', @eId) eq current()/@href]">[AKN-55] noteRef/@href "<value-of select="@href"/>" references a note in meta/notes.</assert>
    </rule>
  </pattern>

  <!-- Section 12: origin and provenance vocabularies. -->
  <pattern id="origin">
    <rule context="*[@cx:origin]">
      <assert test="@cx:origin = ('court', 'reporter', 'publisher', 'producer', 'unknown')">[12.1] @cx:origin is one of court, reporter, publisher, producer, unknown, not "<value-of select="@cx:origin"/>".</assert>
    </rule>
  </pattern>
  <pattern id="provenance">
    <rule context="*[@cx:provenance]">
      <assert test="@cx:provenance = ('source', 'engine-output', 'human-curated')">[12.2] @cx:provenance is one of source, engine-output, human-curated, not "<value-of select="@cx:provenance"/>".</assert>
    </rule>
  </pattern>

  <!-- Section 13.1: decisions with no released text. -->
  <pattern id="no-text">
    <rule context="a:judgment/a:judgmentBody">
      <let name="texts" value="$proprietary/cx:printing/@text"/>
      <let name="no-text" value="exists($texts) and (every $t in $texts satisfies $t = ('withheld', 'unavailable'))"/>
      <assert test="if ($no-text) then (count(*) eq 1 and a:introduction/a:p[@class eq 'no-text'][@cx:origin eq 'producer']) else not(a:introduction)">[AKN-58] <value-of select="if ($no-text) then 'No printing has released text, so judgmentBody is one introduction holding a p of class &quot;no-text&quot; with @cx:origin &quot;producer&quot;.' else 'introduction is used only for a decision with no released text.'"/></assert>
      <assert test="not($no-text) or (every $b in ../a:header/* satisfies $b/@cx:origin eq 'producer')">[13.1] In a decision with no released text, header blocks have @cx:origin "producer".</assert>
    </rule>
  </pattern>
</schema>
